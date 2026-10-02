from datetime import datetime, timezone

from sqlalchemy import func, select

from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db, session_factory
from betmodel.domain import FixtureRecord
from betmodel.ingest import ingest_api_football
from betmodel.models import Fixture, OddsSnapshot
from betmodel.normalize import canonical_live_market
from betmodel.providers.api_football import ApiFootballOdds


def test_canonical_live_market_maps_supported_markets_and_rejects_unknowns():
    home = "Arsenal"
    away = "Chelsea"
    assert canonical_live_market("Match Winner", "Home", home, away) == ("MATCH_HOME", home, None)
    assert canonical_live_market("Match Winner", "Draw", home, away) == ("MATCH_DRAW", "Draw", None)
    assert canonical_live_market("Goals Over/Under", "Over 2.5", home, away) == (
        "TOTAL_GOALS_OVER",
        "Over 2.5",
        2.5,
    )
    assert canonical_live_market("Both Teams Score", "Yes", home, away) == ("BTTS_YES", "Yes", None)
    assert canonical_live_market("Corners Over Under", "Under 9.5", home, away) == (
        "TOTAL_CORNERS_UNDER",
        "Under 9.5",
        9.5,
    )
    assert canonical_live_market("Home Team Total Corners", "Over 4.5", home, away) == (
        "TEAM_CORNERS_OVER",
        "Arsenal Over 4.5",
        4.5,
    )
    assert canonical_live_market("Away Team Shots On Target", "Over 2.5", home, away) == (
        "TEAM_SOT_OVER",
        "Chelsea Over 2.5",
        2.5,
    )
    assert canonical_live_market("Mystery Special", "Yes", home, away) is None


def test_ingest_api_football_is_idempotent_and_skips_unknown_markets(tmp_path):
    settings = Settings(tmp_path)
    engine = create_engine_for(settings)
    init_db(engine)
    fixture = FixtureRecord(
        source="api-football",
        provider_id="123",
        competition="Premier League",
        season="2026",
        kickoff=datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc),
        home_team="Arsenal",
        away_team="Chelsea",
        status="SCHEDULED",
    )
    stamp = datetime(2026, 9, 20, 12, 30, tzinfo=timezone.utc)
    odds = [
        ApiFootballOdds(
            provider_fixture_id="123",
            competition="Premier League",
            season="2026",
            bookmaker="ExampleBook",
            market_name="Match Winner",
            selection="Home",
            decimal_odds=1.80,
            source_timestamp=stamp,
        ),
        ApiFootballOdds(
            provider_fixture_id="123",
            competition="Premier League",
            season="2026",
            bookmaker="ExampleBook",
            market_name="Corners Over Under",
            selection="Over 8.5",
            decimal_odds=1.91,
            source_timestamp=stamp,
        ),
        ApiFootballOdds(
            provider_fixture_id="123",
            competition="Premier League",
            season="2026",
            bookmaker="ExampleBook",
            market_name="Mystery Special",
            selection="Yes",
            decimal_odds=2.00,
            source_timestamp=stamp,
        ),
    ]

    first = ingest_api_football(engine, [fixture], {"123": odds})
    second = ingest_api_football(engine, [fixture], {"123": odds})

    assert first.fixtures == 1
    assert first.team_stat_rows == 0
    assert first.odds_rows == 2
    assert second.odds_rows == 2

    Session = session_factory(engine)
    with Session() as session:
        assert session.scalar(select(func.count(Fixture.id))) == 1
        assert session.scalar(select(func.count(OddsSnapshot.id))) == 2
        markets = session.scalars(select(OddsSnapshot.market_key).order_by(OddsSnapshot.market_key)).all()
        assert markets == ["MATCH_HOME", "TOTAL_CORNERS_OVER"]
