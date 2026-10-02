from datetime import datetime, timezone
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.models import Fixture, OddsSnapshot


def pattern(label, group='Combined unique matches', trials=20):
    return dict(label=label,group=group,hits=trials,trials=trials,rate=1,
                lower=.8,posterior_mean=.95,**{'from':'2026-08-01','to':'2026-09-17'})


def test_exact_market_and_venue_matching():
    from betmodel.historical_suggestions import pattern_market
    m={'home':'Barcelona','away':'Sevilla'}
    assert pattern_market(pattern('Barcelona: 3+ corners (home)','Barcelona'),m)==('TEAM_CORNERS_OVER',2.5,'Barcelona')
    assert pattern_market(pattern('Barcelona: 3+ corners (away)','Barcelona'),m) is None
    assert pattern_market(pattern('Over 0.5 goals'),m)==('TOTAL_GOALS_OVER',.5,None)


def test_suggestions_do_not_need_forecast_or_odds_and_combos_have_no_win_probability(tmp_path):
    from betmodel.historical_suggestions import suggestions, priced_patterns, build_combinations
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    now=datetime(2026,9,19,10,tzinfo=timezone.utc)
    matches=[]
    with session_factory(engine).begin() as s:
        for i in range(2):
            f=Fixture(source='test',provider_id=str(i),competition='La Liga',season='2026',
                      home_team='Barcelona',away_team='Sevilla',status='SCHEDULED',kickoff=datetime(2026,9,19,20))
            s.add(f);s.flush()
            matches.append(dict(fixture_id=f.id,home='Barcelona',away='Sevilla',competition='La Liga',
                status='SCHEDULED',kickoff='2026-09-19T20:00:00Z',forecast={'available':False},
                patterns=[pattern('Over 0.5 goals'),pattern('Barcelona: 3+ corners (home)','Barcelona')],individual=[]))
            s.add(OddsSnapshot(fixture_id=f.id,source='test',bookmaker='A',market_key='TOTAL_GOALS_OVER',
                selection='Over 2.5',line=2.5,decimal_odds=1.45,source_timestamp=now.replace(tzinfo=None)))
    evidence={'matches':matches}
    assert len(suggestions(evidence,now))==2
    assert priced_patterns(engine,evidence,now)==[]  # Over 0.5 evidence cannot support Over 2.5.
    with session_factory(engine).begin() as s:
        for m in matches:
            s.add(OddsSnapshot(fixture_id=m['fixture_id'],source='test',bookmaker='A',market_key='TOTAL_GOALS_OVER',
                selection='Over 0.5',line=.5,decimal_odds=1.45,source_timestamp=now.replace(tzinfo=None)))
    result=build_combinations(priced_patterns(engine,evidence,now))
    assert result['2']
    assert result['2'][0]['joint_probability'] is None
    assert result['2'][0]['ev'] is None
    assert all(l['probability'] is None for l in result['2'][0]['legs'])


def test_league_scope_uses_country_and_includes_championship():
    from betmodel.league_scope import in_scope
    assert in_scope('Championship','England')
    assert in_scope('Super League','Switzerland')
    assert in_scope('Premier League','Armenia')
    assert not in_scope('Premier League','Egypt')
    assert not in_scope('League One','England')
    assert not in_scope('Cup','France')


def test_current_season_import_uses_recent_completed_results(tmp_path):
    import httpx
    from sqlalchemy import select
    from betmodel.history_research import import_current_season
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    csv='Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nSP1,19/09/2026,Barcelona,Sevilla,2,1\nSP1,30/09/2026,Sevilla,Barcelona,,\n'
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=csv))) as http:
        report=import_current_season(engine,tmp_path,http=http,now=datetime(2026,9,19,tzinfo=timezone.utc),codes=['SP1'])
    with session_factory(engine)() as s:
        rows=s.scalars(select(Fixture)).all()
        assert len(rows)==1 and rows[0].match_date.isoformat()=='2026-09-19'
    assert report[0]['latest_result']=='2026-09-19'


def test_explicit_team_goal_market_normalization():
    from betmodel.normalize import canonical_live_market
    assert canonical_live_market('Home Team Total Goals','Over 0.5','Barcelona','Sevilla')==('TEAM_GOALS_OVER','Barcelona Over 0.5',.5)


def test_missing_history_hides_championship_but_keeps_european_top_division(tmp_path):
    from betmodel.dashboard import Dashboard
    from betmodel.domain import FixtureRecord
    from betmodel.ingest import ingest_api_football
    app=Dashboard(tmp_path)
    kickoff=datetime(2026,9,19,20,tzinfo=timezone.utc)
    records=[FixtureRecord('api-football','1','Championship','2026',kickoff,'A','B',country='England',league_id='40'),
             FixtureRecord('api-football','2','Premier League','2026',kickoff,'C','D',country='Egypt'),
             FixtureRecord('api-football','3','Premier League','2026',kickoff,'E','F',country='England',league_id='39')]
    ingest_api_football(app.engine,records,{})
    rows=app.matches('2026-09-19',0,0)['matches']
    assert len(rows)==1 and rows[0]['competition']=='Premier League'
    assert rows[0]['history_home']==0 and rows[0]['odds_count']==0
    from betmodel.models import TeamMatchStat
    with session_factory(app.engine).begin() as s:
        past=Fixture(source='archive',provider_id='past',competition='E1',season='2026',home_team='A',away_team='B',
            status='FINISHED',match_date=datetime(2026,9,1).date())
        s.add(past);s.flush()
        s.add_all([TeamMatchStat(fixture_id=past.id,team_name='A',is_home=1,goals=1),
                   TeamMatchStat(fixture_id=past.id,team_name='B',is_home=0,goals=0)])
    assert len(app.matches('2026-09-19',0,0)['matches'])==2


def test_unpriced_slips_use_separate_upcoming_fixtures_and_no_invented_prices():
    from betmodel.historical_suggestions import build_historical_slips
    now=datetime(2026,9,19,10,tzinfo=timezone.utc)
    matches=[dict(fixture_id=i,home=f'Home{i}',away=f'Away{i}',competition='E0',
                  status='SCHEDULED',kickoff='2026-09-19T20:00:00Z',patterns=[pattern('Over 0.5 goals')]) for i in range(1,5)]
    matches.append(dict(matches[0],fixture_id=99,status='SEARCH',kickoff=None))
    result=build_historical_slips({'matches':matches},now)
    assert result['2'] and result['3']
    for target,slips in result.items():
        for slip in slips:
            assert len(slip['legs'])==int(target)
            assert len({l['fixture_id'] for l in slip['legs']})==int(target)
            assert 99 not in {l['fixture_id'] for l in slip['legs']}
            assert slip['total_odds'] is None and slip['joint_probability'] is None
            assert all(l['odds'] is None and l['bookmaker'] is None for l in slip['legs'])
    assert not build_historical_slips({'matches':matches[:1]},now)['2']


def test_historical_cohort_does_not_invent_probabilities_and_freezes_patterns(tmp_path):
    from betmodel.performance import record_combinations,performance_summary,prediction_history
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    now=datetime(2026,9,19,10,tzinfo=timezone.utc)
    with session_factory(engine).begin() as s:
        f=Fixture(source='test',provider_id='1',competition='E0',season='2026',home_team='A',away_team='B',
                  status='SCHEDULED',kickoff=datetime(2026,9,19,20))
        s.add(f);s.flush();fid=f.id
    leg=dict(fixture_id=fid,market_key='TOTAL_GOALS_OVER',selection='Over 0.5',line=.5,odds=2,bookmaker='A',patterns=[pattern('Over 0.5 goals')])
    item=dict(legs=[leg],joint_probability=None,model_version='historical-pattern-v2')
    assert record_combinations(engine,'2','historical',[item],now)==1
    leg['patterns'][0]['trials']=10
    assert record_combinations(engine,'2','historical',[item],now)==0
    assert performance_summary(engine)['historical']['2']['generated']==1
    rows=prediction_history(engine,(datetime(2026,9,19,tzinfo=timezone.utc),datetime(2026,9,20,tzinfo=timezone.utc)),'historical')['items']
    assert rows[0]['joint_probability'] is None
    assert rows[0]['legs'][0]['patterns'][0]['trials']==20
