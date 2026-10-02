from datetime import datetime, timezone
from betmodel.dashboard import Dashboard
from test_dashboard import seed_database


def test_rejected_candidates_are_not_recorded_as_recommendations(tmp_path):
    app=Dashboard(tmp_path)
    seed_database(app.engine)
    now=datetime(2026,9,17,12,tzinfo=timezone.utc)
    app.analyze('2026-09-17',0,0,now=now)
    first=app.performance()['cohorts']['model']['2']
    assert first['generated']==0
    assert first['win_rate'] is None
    app.analyze('2026-09-17',0,0,now=now)
    assert app.performance()['cohorts']['model']['2']['generated']==first['generated']


def test_learning_and_result_jobs_are_available_without_key(tmp_path):
    app=Dashboard(tmp_path)
    assert app.start('results','2026-09-18',0,0)
    app.worker.join(10)
    assert app.status()['job']['state']=='done'
    assert app.start('learn','2026-09-18',0,0)
    app.worker.join(10)
    assert app.status()['job']['state']=='done'


def test_recommendations_explain_missing_history(tmp_path):
    app=Dashboard(tmp_path)
    seed_database(app.engine)
    data=app.insights('2026-09-17',0,0,recommendations=True)
    assert data['diagnostics']
    assert all('reason' in row and 'fixture' in row for row in data['diagnostics'])


def test_daily_resolves_archive_team_aliases(tmp_path):
    from sqlalchemy import select
    from betmodel.db import session_factory
    from betmodel.models import Fixture
    app=Dashboard(tmp_path)
    seed_database(app.engine)
    with session_factory(app.engine).begin() as s:
        for f in s.scalars(select(Fixture)):
            if f.home_team=='Strong1':f.home_team='Manchester United' if f.status=='SCHEDULED' else 'Man United'
            if f.away_team=='Strong1':f.away_team='Man United'
    from betmodel.daily import run_daily_pipeline
    from datetime import date
    result=run_daily_pipeline(app.engine,date(2026,9,17),datetime(2026,9,17,12,tzinfo=timezone.utc),tmp_path/'previews')
    assert any('Manchester United' in leg.fixture_key for c in result.combinations_2x for leg in c.legs)


def test_price_pages_save_one_immutable_cohort(tmp_path):
    app=Dashboard(tmp_path)
    seed_database(app.engine)
    now=datetime(2026,9,17,12,tzinfo=timezone.utc)
    page=app.price_combinations('2026-09-17',0,0,'2',now=now)
    assert page['total']==0
    app.price_combinations('2026-09-17',0,0,'2',now=now)
    data=app.performance()['cohorts']
    assert data['odds-only']['2']['generated']==0
    assert data['odds-only']['2']['win_rate'] is None
    assert data['model']['2']['generated']==0


def test_dashboard_current_policy_excludes_legacy_model_records(tmp_path):
    app=Dashboard(tmp_path)
    from betmodel.performance import record_combinations
    now=datetime(2026,9,17,12,tzinfo=timezone.utc)
    record_combinations(app.engine,2,'model',[{'legs':[],'joint_probability':.6,'model_version':'poisson-baseline-v1'}],now)
    assert app.performance()['cohorts']['model']['2']['generated']==0
