import hashlib
import pytest
from sqlalchemy import insert,select
from betmodel.config import Settings
from betmodel.db import create_engine_for,init_db
from betmodel.models import Fixture


def test_snapshot_and_transactional_import(tmp_path):
    from betmodel.migrate_cloud import backup_sqlite,migrate_snapshot,table_counts
    settings=Settings(tmp_path/'source');source=create_engine_for(settings);init_db(source)
    with source.begin() as c:
        c.execute(insert(Fixture).values(id=12,source='test',provider_id='1',competition='E0',season='2026',home_team='A',away_team='B'))
    source.dispose()
    before=hashlib.sha256(settings.database_path.read_bytes()).hexdigest()
    snapshot=backup_sqlite(settings.database_path,tmp_path/'copy.db')
    target=create_engine_for(Settings(tmp_path/'target'));init_db(target)
    result=migrate_snapshot(snapshot,target,dry_run=True)
    assert result['counts']['fixtures']==1 and table_counts(target)['fixtures']==0
    migrate_snapshot(snapshot,target,dry_run=False)
    assert table_counts(target)['fixtures']==1
    with pytest.raises(ValueError,match='empty'):migrate_snapshot(snapshot,target,dry_run=False)
    assert hashlib.sha256(settings.database_path.read_bytes()).hexdigest()==before


def test_migration_preserves_report_from_local_cache(tmp_path):
    import json
    from betmodel.migrate_cloud import migrate_snapshot
    from betmodel.state_store import load_state
    root=tmp_path/'source';settings=Settings(root);source=create_engine_for(settings);init_db(source);source.dispose()
    folder=root/'data/raw/research';folder.mkdir(parents=True)
    (folder/'report.json').write_text(json.dumps({'updated':'2026-09-19','sources':[],'messages':['saved']}))
    target=create_engine_for(Settings(tmp_path/'target'))
    migrate_snapshot(settings.database_path,target,dry_run=False,state_root=root)
    assert load_state(target,'research-report')['messages']==['saved']
