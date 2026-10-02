from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from betmodel.config import Settings
from betmodel.daily import run_daily_pipeline
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.models import Fixture, OddsSnapshot, Prediction, TeamMatchStat

NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)


def _add_match(session, idx: int, match_date: date, home: str, away: str, home_corners, away_corners, home_sot, away_sot):
    fixture = Fixture(
        source="synthetic-count",
        provider_id=f"hist-{idx}",
        competition="TEST",
        season="2026",
        match_date=match_date,
        home_team=home,
        away_team=away,
        status="FINISHED",
    )
    session.add(fixture)
    session.flush()
    session.add_all(
        [
            TeamMatchStat(
                fixture_id=fixture.id,
                team_name=home,
                is_home=1,
                goals=2,
                shots=15,
                shots_on_target=home_sot,
                corners=home_corners,
                cards=2,
            ),
            TeamMatchStat(
                fixture_id=fixture.id,
                team_name=away,
                is_home=0,
                goals=1,
                shots=8,
                shots_on_target=away_sot,
                corners=away_corners,
                cards=3,
            ),
        ]
    )


def _seed_count_history(session, missing_corners: bool = False):
    for i in range(8):
        day = date(2026, 7, 1) + timedelta(days=i * 4)
        # Alpha at home produces heavy corners/SOT against rotating opponents.
        _add_match(
            session,
            i,
            day,
            "Alpha",
            f"Other{i}",
            None if missing_corners else 7,
            None if missing_corners else 3,
            6,
            2,
        )
        # Beta away tends to concede corners/SOT to the home side.
        _add_match(
            session,
            100 + i,
            day + timedelta(days=1),
            f"Host{i}",
            "Beta",
            None if missing_corners else 6,
            None if missing_corners else 2,
            5,
            2,
        )


def _add_target(session, market_rows):
    fixture = Fixture(
        source="api-football",
        provider_id="target",
        competition="TEST",
        season="2026",
        match_date=date(2026, 9, 17),
        kickoff=NOW.replace(tzinfo=None) + timedelta(hours=6),
        home_team="Alpha",
        away_team="Beta",
        status="SCHEDULED",
    )
    session.add(fixture)
    session.flush()
    for market_key, selection, line, odds in market_rows:
        session.add(
            OddsSnapshot(
                fixture_id=fixture.id,
                source="api-football",
                bookmaker="ExampleBook",
                market_key=market_key,
                selection=selection,
                line=line,
                decimal_odds=odds,
                received_timestamp=NOW.replace(tzinfo=None),
            )
        )


def test_daily_pipeline_models_corners_and_team_sot_when_history_exists(tmp_path):
    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    Session = session_factory(engine)
    with Session.begin() as session:
        _seed_count_history(session)
        _add_target(
            session,
            [
                ("TOTAL_CORNERS_OVER", "Over 8.5", 8.5, 1.90),
                ("TEAM_SOT_OVER", "Alpha Over 3.5", 3.5, 1.75),
            ],
        )

    result = run_daily_pipeline(
        engine,
        report_date=date(2026, 9, 17),
        now=NOW,
        preview_dir=tmp_path / "previews",
        max_price_age=timedelta(hours=24),
    )

    assert result.report.valid_candidates == 2
    with Session() as session:
        predictions = session.scalars(select(Prediction).order_by(Prediction.market_key)).all()
        assert [p.market_key for p in predictions] == ["TEAM_SOT_OVER", "TOTAL_CORNERS_OVER"]
        assert all(0 < p.probability < 1 for p in predictions)


def test_daily_pipeline_skips_corner_market_when_corner_history_missing(tmp_path):
    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    Session = session_factory(engine)
    with Session.begin() as session:
        _seed_count_history(session, missing_corners=True)
        _add_target(session, [("TOTAL_CORNERS_OVER", "Over 8.5", 8.5, 1.90)])

    result = run_daily_pipeline(
        engine,
        report_date=date(2026, 9, 17),
        now=NOW,
        preview_dir=tmp_path / "previews",
        max_price_age=timedelta(hours=24),
    )

    assert result.report.valid_candidates == 0
