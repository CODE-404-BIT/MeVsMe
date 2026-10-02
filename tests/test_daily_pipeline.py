from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest

from sqlalchemy import func, select

from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.daily import run_daily_pipeline
from betmodel.models import Fixture, OddsSnapshot, Prediction, Recommendation, RecommendationLeg, TeamMatchStat

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def add_finished(session, provider_id, match_date, home, away, hg, ag):
    f = Fixture(
        source="synthetic",
        provider_id=provider_id,
        competition="TEST",
        season="2026",
        match_date=match_date,
        home_team=home,
        away_team=away,
        status="FINISHED",
    )
    session.add(f)
    session.flush()
    session.add_all([
        TeamMatchStat(fixture_id=f.id, team_name=home, is_home=1, goals=hg, shots=14, shots_on_target=6, corners=6, cards=2),
        TeamMatchStat(fixture_id=f.id, team_name=away, is_home=0, goals=ag, shots=7, shots_on_target=2, corners=3, cards=3),
    ])


def seed_database(engine):
    Session = session_factory(engine)
    with Session.begin() as session:
        for i in range(1, 6):
            h, a = f"Strong{i}", f"Weak{i}"
            add_finished(session, f"h{i}-1", date(2026, 8, 1), h, a, 3, 0)
            add_finished(session, f"h{i}-2", date(2026, 8, 8), h, a, 2, 0)
            add_finished(session, f"a{i}-1", date(2026, 8, 15), a, h, 0, 2)
            add_finished(session, f"a{i}-2", date(2026, 8, 22), a, h, 1, 3)

            target = Fixture(
                source="synthetic",
                provider_id=f"target-{i}",
                competition="TEST",
                season="2026",
                match_date=date(2026, 9, 17),
                kickoff=NOW.replace(tzinfo=None) + timedelta(hours=5 + i),
                home_team=h,
                away_team=a,
                status="SCHEDULED",
            )
            session.add(target)
            session.flush()
            session.add(OddsSnapshot(
                fixture_id=target.id,
                source="free-test-feed",
                bookmaker="Reference",
                market_key="MATCH_HOME",
                selection=h,
                decimal_odds=1.45,
                received_timestamp=NOW.replace(tzinfo=None),
            ))


def test_daily_pipeline_builds_and_saves_2x_3x_email(tmp_path: Path):
    settings = Settings(tmp_path)
    engine = create_engine_for(settings)
    init_db(engine)
    seed_database(engine)

    result = run_daily_pipeline(
        engine,
        report_date=date(2026, 9, 17),
        now=NOW,
        preview_dir=tmp_path / "previews",
        max_price_age=timedelta(hours=24),
    )

    assert result.report.best_2x is not None
    assert result.report.best_3x is not None
    assert 1.80 <= result.report.best_2x.total_odds <= 2.30
    assert 2.60 <= result.report.best_3x.total_odds <= 3.50
    assert result.text_path.exists()
    assert result.html_path.exists()

    Session = session_factory(engine)
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(Prediction)) == 5
        assert session.scalar(select(func.count()).select_from(Recommendation)) == 2
        assert session.scalar(select(func.count()).select_from(RecommendationLeg)) == 5


@pytest.mark.parametrize("missing_side", ["home_team", "away_team"])
def test_daily_excludes_matches_when_either_team_has_no_history(tmp_path, missing_side):
    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    seed_database(engine)
    Session = session_factory(engine)
    with Session.begin() as session:
        for fixture in session.scalars(select(Fixture).where(Fixture.status == "SCHEDULED")):
            setattr(fixture, missing_side, "Unseen team")
    result = run_daily_pipeline(engine, date(2026, 9, 17), NOW, tmp_path / "previews")
    assert result.report.scanned_markets == 5
    assert result.report.valid_candidates == 0
    assert result.report.best_2x is None
    assert result.report.best_3x is None
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(Prediction)) == 0
