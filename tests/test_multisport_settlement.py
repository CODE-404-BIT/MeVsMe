from datetime import datetime,timezone
from betmodel.config import Settings
from betmodel.db import create_engine_for,init_db
from betmodel.multisport_store import upsert_events,event_key,freeze_predictions

NOW=datetime(2026,10,2,10,tzinfo=timezone.utc)


def test_new_sport_snapshots_settle_once_without_rewriting_prediction(tmp_path):
    from betmodel.multisport_settlement import settle_sports,sport_performance
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    row=dict(sport='basketball',provider='test',provider_id='1',competition='NBA',scope='including_overtime',
        home='A',away='B',home_id='a',away_id='b',start='2026-10-02T20:00:00Z',status='SCHEDULED')
    row['event_key']=event_key(row)
    upsert_events(engine,[row])
    pick=dict(row,market='winner',selection='A',model_version='test-v1',cutoff=NOW.isoformat(),probability=.7)
    freeze_predictions(engine,[pick],NOW)
    assert settle_sports(engine,NOW)==0
    upsert_events(engine,[dict(row,status='FINISHED',home_score=100,away_score=90)])
    assert settle_sports(engine,datetime(2026,10,3,tzinfo=timezone.utc))==1
    assert settle_sports(engine,datetime(2026,10,3,tzinfo=timezone.utc))==0
    assert sport_performance(engine)['model']['won']==1


def test_historical_sport_combination_requires_all_verified_legs(tmp_path):
    from betmodel.multisport_settlement import freeze_sport_combinations,settle_sports,sport_performance
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    row=dict(sport='icehockey',provider='test',provider_id='1',competition='NHL',scope='including_overtime',
        home='A',away='B',home_id='a',away_id='b',start='2026-10-02T20:00:00Z',status='FINISHED',home_score=3,away_score=2)
    row['event_key']=event_key(row)
    upsert_events(engine,[row])
    leg=dict(event_key=row['event_key'],market='winner',selection='A',scope='including_overtime',odds=1.45,updated=NOW.isoformat())
    combo={'legs':[leg,dict(leg,event_key='unresolved')],'total_odds':2.1025}
    freeze_sport_combinations(engine,{'2':[combo],'3':[]},NOW)
    assert settle_sports(engine,datetime(2026,10,3,tzinfo=timezone.utc))==0
    assert sport_performance(engine)['historical']['pending']==1


def test_all_potential_filter_picks_have_frozen_snapshots(tmp_path,monkeypatch):
    from betmodel.multisport_recommendations import prepare_recommendations
    from betmodel.multisport_settlement import sport_performance
    from datetime import timedelta
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    rows=[dict(event_key=str(i),sport='basketball',status='SCHEDULED',start='2026-10-02T20:00:00Z',
        home='A',away='B',market='winner',selection='A',model_version='test',cutoff=NOW.isoformat(),
        probability=.7+i/1000,validated=True,sample_home=20,sample_away=20,
        latest_home='2026-10-01',latest_away='2026-10-01') for i in range(11)]
    monkeypatch.setattr('betmodel.multisport_recommendations.sport_candidates',lambda *args:(rows,[]))
    monkeypatch.setattr('betmodel.multisport_recommendations.football_candidates',lambda *args:[])
    assert prepare_recommendations(engine,(NOW,NOW+timedelta(days=1)),NOW)==10
    assert sport_performance(engine)['model']['generated']==11


def test_different_bookmakers_do_not_share_combination_snapshot(tmp_path):
    from betmodel.multisport_settlement import freeze_sport_combinations,sport_performance
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    leg=dict(event_key='1',market='winner',selection='A',scope='including_overtime',odds=1.45,
             updated=NOW.isoformat(),bookmaker='First')
    first={'legs':[leg,dict(leg,event_key='2')],'total_odds':2.1025,'bookmaker':'First'}
    second=dict(first,bookmaker='Second',legs=[dict(row,bookmaker='Second') for row in first['legs']])
    freeze_sport_combinations(engine,{'2':[first,second],'3':[]},NOW)
    assert sport_performance(engine)['historical']['generated']==2
