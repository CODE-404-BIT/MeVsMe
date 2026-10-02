"""Additive sport-aware records. Football's existing tables and IDs are unchanged."""
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite

from sqlalchemy import Table, Column, MetaData, String, JSON, DateTime, select
from .db import conflict_insert

SPORTS=('football','basketball','tennis','icehockey')
metadata=MetaData()
events=Table('sport_events',metadata,
    Column('key',String(240),primary_key=True),Column('sport',String(24),index=True,nullable=False),
    Column('start',DateTime,index=True,nullable=False),Column('payload',JSON,nullable=False))
quotes=Table('sport_quotes',metadata,
    Column('key',String(240),primary_key=True),Column('event_key',String(240),index=True,nullable=False),
    Column('payload',JSON,nullable=False))
snapshots=Table('sport_predictions',metadata,
    Column('key',String(240),primary_key=True),Column('event_key',String(240),index=True,nullable=False),
    Column('created_at',DateTime,nullable=False),Column('payload',JSON,nullable=False))


def utc(value):
    value=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
    if not isinstance(value,datetime) or value.tzinfo is None:raise ValueError('An explicit UTC offset is required')
    return value.astimezone(timezone.utc)


def event_key(row):
    # Separators in provider IDs cannot cause collisions.
    return hashlib.sha256(json.dumps([row['sport'],row['provider'],str(row['provider_id'])]).encode()).hexdigest()


def validate_event(row):
    if row.get('sport') not in SPORTS:raise ValueError('Unsupported sport')
    for field in ('provider','provider_id','competition','home','away','home_id','away_id','scope'):
        if row.get(field) is None or not str(row.get(field,'')).strip() or str(row.get(field)).lower() in {'none','null'}:
            raise ValueError('Incomplete event identity')
    if row['home_id']==row['away_id']:raise ValueError('Event participants must differ')
    if row.get('status') not in {'SCHEDULED','FINISHED','LIVE','CANCELLED','POSTPONED'}:raise ValueError('Unknown event status')
    utc(row['start'])
    if row['status']=='FINISHED':
        for field in ('home_score','away_score'):
            value=row.get(field)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or value<0:
                raise ValueError('A final result requires complete scores')
    json.dumps(row,allow_nan=False)


def upsert_events(engine, rows):
    rows=list(rows)
    for row in rows:validate_event(row)
    with engine.begin() as connection:
        for row in rows:
            payload=dict(row,event_key=event_key(row))
            previous=connection.scalar(select(events.c.payload).where(events.c.key==payload['event_key']))
            if previous and previous.get('observed_at') and row.get('observed_at') and utc(previous['observed_at'])>utc(row['observed_at']):continue
            statement=conflict_insert(events,engine).values(key=payload['event_key'],sport=row['sport'],
                start=utc(row['start']).replace(tzinfo=None),payload=payload)
            connection.execute(statement.on_conflict_do_update(index_elements=['key'],
                set_={'payload':payload,'start':utc(row['start']).replace(tzinfo=None)}))
    return len(rows)


def load_events(engine, sport=None, window=None):
    statement=select(events.c.payload).order_by(events.c.start,events.c.key)
    if sport:statement=statement.where(events.c.sport==sport)
    if window:statement=statement.where(events.c.start>=utc(window[0]).replace(tzinfo=None),
                                       events.c.start<utc(window[1]).replace(tzinfo=None))
    with engine.connect() as connection:return list(connection.scalars(statement))


def upsert_quotes(engine, rows):
    rows=list(rows)
    for row in rows:
        if not row.get('event_key') or not row.get('bookmaker') or not row.get('scope'):raise ValueError('Incomplete quote')
        if not isfinite(row['odds']) or row['odds']<=1:raise ValueError('Invalid decimal price')
        utc(row['updated'])
        json.dumps(row,allow_nan=False)
    with engine.begin() as connection:
        for row in rows:
            identity=[row.get(k) for k in ('event_key','bookmaker','market','selection','line','scope')]
            key=hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            previous=connection.scalar(select(quotes.c.payload).where(quotes.c.key==key))
            if previous and utc(previous['updated'])>utc(row['updated']):continue
            statement=conflict_insert(quotes,engine).values(key=key,event_key=row['event_key'],payload=row)
            connection.execute(statement.on_conflict_do_update(index_elements=['key'],set_={'payload':row}))
    return len(rows)


def load_quotes(engine):
    with engine.connect() as connection:return list(connection.scalars(select(quotes.c.payload)))


def freeze_predictions(engine, rows, now):
    with engine.begin() as connection:
        for row in rows:
            identity=[row['event_key'],row['market'],row['selection'],row['model_version'],row['cutoff']]
            key=hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            statement=conflict_insert(snapshots,engine).values(key=key,event_key=row['event_key'],
                created_at=utc(now).replace(tzinfo=None),payload=row)
            connection.execute(statement.on_conflict_do_nothing(index_elements=['key']))
