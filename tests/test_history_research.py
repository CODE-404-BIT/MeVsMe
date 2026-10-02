from datetime import datetime, timezone
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.models import Fixture, OddsSnapshot, TeamMatchStat
from betmodel.domain import FixtureRecord
from betmodel.ingest import ingest_api_football
from sqlalchemy import select, func
from betmodel.history_research import ingest_results


def test_skipped_odds_fetch_preserves_saved_prices(tmp_path):
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    record=FixtureRecord('api-football','1','Test','2026',datetime(2026,9,18,tzinfo=timezone.utc),'A','B')
    ingest_api_football(engine,[record],{})
    with session_factory(engine).begin() as s:
        f=s.scalar(select(Fixture))
        s.add(OddsSnapshot(fixture_id=f.id,source='api-football',market_key='MATCH_HOME',selection='A',decimal_odds=2))
    ingest_api_football(engine,[record],{})
    with session_factory(engine)() as s:
        assert s.scalar(select(func.count()).select_from(OddsSnapshot))==1


def test_result_import_is_idempotent_and_uses_fulltime_not_extra_time(tmp_path):
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    row={'fixture':{'id':77,'date':'2026-08-01T12:00:00+00:00','status':{'short':'AET'}},
         'league':{'id':39,'name':'Premier League','season':2026},
         'teams':{'home':{'name':'Arsenal'},'away':{'name':'Chelsea'}},
         'goals':{'home':3,'away':2},'score':{'fulltime':{'home':1,'away':1}}}
    cutoff=datetime(2026,9,1,tzinfo=timezone.utc)
    assert ingest_results(engine,[row],cutoff)==1
    assert ingest_results(engine,[row],cutoff)==1
    with session_factory(engine)() as s:
        assert s.scalar(select(func.count()).select_from(Fixture))==1
        assert [r.goals for r in s.scalars(select(TeamMatchStat))]==[1,1]
    assert ingest_results(engine,[row],datetime(2026,7,1,tzinfo=timezone.utc))==0
