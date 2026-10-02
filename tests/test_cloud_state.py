from datetime import datetime, timedelta, timezone
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db
from betmodel.state_store import load_state, save_state, job_guard


def test_state_survives_restart_and_expires(tmp_path):
    engine = create_engine_for(Settings(tmp_path)); init_db(engine)
    now = datetime.now(timezone.utc)
    save_state(engine, 'research-report', {'messages': ['saved']})
    save_state(engine, 'expired', {'secret': 'not returned'}, now-timedelta(seconds=1))
    engine.dispose()
    second = create_engine_for(Settings(tmp_path))
    assert load_state(second, 'research-report', now)['messages'] == ['saved']
    assert load_state(second, 'expired', now) is None
    save_state(second, 'research-report', {'messages': ['updated']})
    assert load_state(second, 'research-report', now)['messages'] == ['updated']


def test_job_guard_excludes_second_owner(tmp_path):
    engine = create_engine_for(Settings(tmp_path)); init_db(engine)
    with job_guard(engine) as first:
        assert first
        with job_guard(engine) as second:
            assert not second
    with job_guard(engine) as third:
        assert third


def test_dashboard_recovers_interrupted_job(tmp_path):
    from betmodel.dashboard import Dashboard
    first = Dashboard(tmp_path)
    save_state(first.engine, 'dashboard-job', {'state':'running','kind':'research','message':'working'})
    second = Dashboard(tmp_path)
    assert second.status()['job']['state'] == 'interrupted'


def test_rolling_restart_observes_completion_and_disappearance(tmp_path):
    from betmodel.dashboard import Dashboard
    first=Dashboard(tmp_path)
    with job_guard(first.engine) as acquired:
        assert acquired
        save_state(first.engine,'dashboard-job',{'state':'running','kind':'research','message':'working'})
        replacement=Dashboard(tmp_path)
        assert replacement.status()['job']['state']=='running'
        save_state(first.engine,'dashboard-job',{'state':'done','kind':'research','message':'complete'})
    assert replacement.status()['job']['state']=='done'
    with job_guard(first.engine):
        save_state(first.engine,'dashboard-job',{'state':'running','kind':'research','message':'working'})
        replacement=Dashboard(tmp_path)
    assert replacement.status()['job']['state']=='interrupted'


import pytest
@pytest.mark.parametrize('failure',['quota','checkpoint','thread'])
def test_start_failure_releases_guard(tmp_path,monkeypatch,failure):
    from betmodel.dashboard import Dashboard
    import threading
    app=Dashboard(tmp_path)
    def fail(*args,**kwargs):raise RuntimeError('Injected startup failure')
    if failure=='quota':monkeypatch.setattr(app,'_restore_quota',fail)
    elif failure=='checkpoint':monkeypatch.setattr(app,'_checkpoint',fail)
    else:monkeypatch.setattr(threading.Thread,'start',fail)
    with pytest.raises(RuntimeError,match='Injected'):app.start('analyze','2026-09-19',0,0)
    with job_guard(app.engine) as acquired:assert acquired
    assert app.job['state']!='running'
