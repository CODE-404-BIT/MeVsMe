from datetime import datetime, timezone, timedelta
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.models import Fixture, OddsSnapshot
from betmodel.odds_only import price_combinations


def test_prices_without_research_are_blocked(tmp_path):
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    now=datetime(2026,9,17,10,tzinfo=timezone.utc)
    with session_factory(engine).begin() as s:
        for i in range(3):
            f=Fixture(source='test',provider_id=str(i),competition='Test',season='2026',home_team=f'H{i}',away_team=f'A{i}',status='SCHEDULED',kickoff=now+timedelta(hours=2),match_date=now.date())
            s.add(f);s.flush()
            s.add(OddsSnapshot(fixture_id=f.id,source='test',bookmaker='Book',market_key='MATCH_HOME',selection=f'H{i}',decimal_odds=1.45,received_timestamp=now))
    window=(now-timedelta(hours=10),now+timedelta(hours=14))
    result=price_combinations(engine,window,'2',now)
    assert result['items']==[]
    assert result['researched'] is True
    assert 'exact markets have fresh prices' in result['research_report']
    assert price_combinations(engine,window,'3',now)['items']==[]
    assert not price_combinations(engine,window,'2',now+timedelta(days=2))['items']
