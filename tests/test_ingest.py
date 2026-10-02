from pathlib import Path
from sqlalchemy import func, select

from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.ingest import ingest_football_data_uk
from betmodel.models import Fixture, OddsSnapshot, TeamMatchStat

FIXTURE = Path(__file__).parent / "fixtures" / "football_data_uk_sample.csv"


def test_ingest_is_idempotent(tmp_path):
    settings = Settings(tmp_path)
    engine = create_engine_for(settings)
    init_db(engine)
    ingest_football_data_uk(engine, FIXTURE, competition="E0", season="2026-27")
    ingest_football_data_uk(engine, FIXTURE, competition="E0", season="2026-27")

    Session = session_factory(engine)
    with Session() as session:
        fixture_count = session.scalar(select(func.count()).select_from(Fixture))
        stat_count = session.scalar(select(func.count()).select_from(TeamMatchStat))
        odds_count = session.scalar(select(func.count()).select_from(OddsSnapshot))

    assert fixture_count == 2
    assert stat_count == 4
    assert odds_count == 10
