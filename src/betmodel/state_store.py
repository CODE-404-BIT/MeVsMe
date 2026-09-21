"""Small durable checkpoints; provider secrets are never stored here."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
import hashlib
import threading
from sqlalchemy import Table, Column, MetaData, String, JSON, DateTime, select, text, delete
from .db import conflict_insert

state = Table('dashboard_state', MetaData(), Column('key', String(240), primary_key=True),
              Column('payload', JSON, nullable=False), Column('expires_at', DateTime))
_locks = {}
_locks_guard = threading.Lock()
JOB_LOCK = 78642102


def load_state(engine, key, now=None):
    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    with engine.connect() as connection:
        row = connection.execute(select(state).where(state.c.key == key)).mappings().first()
    if not row or (row['expires_at'] and row['expires_at'] <= now):
        return None
    return row['payload']


def save_state(engine, key, payload, expires_at=None):
    expires = expires_at.astimezone(timezone.utc).replace(tzinfo=None) if expires_at else None
    statement = conflict_insert(state, engine).values(key=key, payload=payload, expires_at=expires)
    statement = statement.on_conflict_do_update(index_elements=['key'],
                set_={'payload': payload, 'expires_at': expires})
    with engine.begin() as connection:
        connection.execute(delete(state).where(state.c.expires_at<=datetime.now(timezone.utc).replace(tzinfo=None)))
        connection.execute(statement)


def quota_key(key):
    return 'quota:' + hashlib.sha256(key.encode()).hexdigest()


def cached_provider_request(engine, key, path, params, fetch):
    identity = json.dumps([quota_key(key),path,params],sort_keys=True)
    cache_key = 'provider:' + hashlib.sha256(identity.encode()).hexdigest()
    cached = load_state(engine,cache_key)
    if cached:
        if cached.get('blocked'):raise RuntimeError('Provider rejected this season query.')
        return cached['rows']
    expires = datetime.now(timezone.utc)+timedelta(hours=24)
    try:
        rows=fetch()
    except RuntimeError as exc:
        if 'season' in str(exc).lower():save_state(engine,cache_key,{'blocked':True},expires)
        raise
    save_state(engine,cache_key,{'rows':rows},expires)
    return rows


@contextmanager
def job_guard(engine):
    if engine.dialect.name == 'postgresql':
        # A dedicated session owns the advisory lock until work finishes.
        with engine.connect() as connection:
            acquired = bool(connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': JOB_LOCK}))
            connection.commit()
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': JOB_LOCK})
                    connection.commit()
    else:
        with _locks_guard:
            lock = _locks.setdefault(str(engine.url), threading.Lock())
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()
