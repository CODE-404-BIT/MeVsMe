"""Integration tests require an explicitly disposable TEST_POSTGRES_URL."""
import os
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, text, insert, select, event
from betmodel.db import init_db, application_tables, conflict_insert
from betmodel.models import Fixture
from betmodel.state_store import job_guard, save_state, load_state
from betmodel.migrate_cloud import migrate_snapshot, table_counts


@pytest.fixture
def pg_engine():
    url=os.getenv('TEST_POSTGRES_URL')
    if not url:pytest.skip('TEST_POSTGRES_URL missing: actual PostgreSQL verification not run')
    engine=create_engine(url)
    # Only isolated random schemas are created; never drop shared application tables.
    import uuid
    schema='test_'+uuid.uuid4().hex
    with engine.begin() as c:c.execute(text('CREATE SCHEMA '+schema))
    engine.dispose()
    engine=create_engine(url,connect_args={'options':'-csearch_path='+schema})
    init_db(engine)
    yield engine
    engine.dispose()
    cleanup=create_engine(url)
    with cleanup.begin() as c:c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
    cleanup.dispose()


def test_postgres_json_dates_upsert_and_lock(pg_engine):
    save_state(pg_engine,'test',{'null':None,'list':[1,2]})
    save_state(pg_engine,'test',{'null':None,'list':[3]})
    assert load_state(pg_engine,'test')['list']==[3]
    with job_guard(pg_engine) as first:
        assert first
        with job_guard(pg_engine) as second:assert not second
    with job_guard(pg_engine) as third:assert third
    from betmodel.performance import saved_combinations
    statement=conflict_insert(saved_combinations,pg_engine).values(identity='unique-test',target='2',mode='historical',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),legs=[{'patterns':[{'hits':5,'trials':5}]}],joint_probability=None
        ).on_conflict_do_nothing(index_elements=['identity'])
    with pg_engine.begin() as c:
        c.execute(statement);c.execute(statement)
        rows=c.execute(select(saved_combinations)).mappings().all()
        assert len(rows)==1 and rows[0]['joint_probability'] is None


def test_real_backup_migration_and_sequences(pg_engine):
    from pathlib import Path
    snapshot=Path('data/backups/pre-cloud-20260919T103426077122Z.db')
    if not snapshot.exists():pytest.skip('Private local backup not available')
    expected=migrate_snapshot(snapshot,None)['counts']
    migrate_snapshot(snapshot,pg_engine,dry_run=False)
    assert table_counts(pg_engine)==expected
    with pytest.raises(ValueError,match='empty'):migrate_snapshot(snapshot,pg_engine,dry_run=False)
    with pg_engine.begin() as c:
        new=c.execute(insert(Fixture).values(source='sequence-test',provider_id='new',competition='E0',
            season='2026',home_team='A',away_team='B').returning(Fixture.id)).scalar_one()
        assert new>1


def test_import_rolls_back_on_error(tmp_path,pg_engine):
    from betmodel.config import Settings
    from betmodel.db import create_engine_for
    source=create_engine_for(Settings(tmp_path));init_db(source)
    with source.begin() as c:c.execute(insert(Fixture).values(id=10,source='test',provider_id='1',competition='E0',season='2026',home_team='A',away_team='B'))
    source.dispose()
    def reject(connection,cursor,statement,parameters,context,executemany):
        if statement.startswith('SELECT count(*)') and 'fixtures' in statement and connection.info.get('inserted'):
            raise RuntimeError('Injected verification failure')
        if statement.startswith('INSERT INTO fixtures'):connection.info['inserted']=True
    event.listen(pg_engine,'before_cursor_execute',reject)
    with pytest.raises(RuntimeError,match='Injected'):migrate_snapshot(tmp_path/'data/app.db',pg_engine,dry_run=False)
    event.remove(pg_engine,'before_cursor_execute',reject)
    assert not any(table_counts(pg_engine).values())
