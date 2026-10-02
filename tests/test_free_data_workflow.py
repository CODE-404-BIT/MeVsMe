from pathlib import Path
import shutil

from sqlalchemy import func, select

from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.free_data import fetch_latest_fixtures, fetch_season_league
from betmodel.models import Fixture

FIXTURE = Path(__file__).parent / "fixtures" / "football_data_uk_sample.csv"


def copier(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE, destination)
    return destination


def test_fetch_latest_downloads_and_ingests_multi_league_file(tmp_path):
    settings = Settings(tmp_path)
    engine = create_engine_for(settings)
    init_db(engine)
    summary = fetch_latest_fixtures(engine, settings, season="2026-27", downloader=copier)
    assert summary.fixtures == 2
    Session = session_factory(engine)
    with Session() as session:
        comps = set(session.scalars(select(Fixture.competition)).all())
    assert comps == {"E0", "E1"}


def test_fetch_season_league_ingests_with_requested_league(tmp_path):
    settings = Settings(tmp_path)
    engine = create_engine_for(settings)
    init_db(engine)
    summary = fetch_season_league(engine, settings, season_code="2627", season="2026-27", league_code="E0", downloader=copier)
    assert summary.fixtures == 2
    Session = session_factory(engine)
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(Fixture)) == 2
        comps = set(session.scalars(select(Fixture.competition)).all())
    assert comps == {"E0"}
