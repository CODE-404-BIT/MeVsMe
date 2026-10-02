from datetime import datetime, timezone
import httpx
import pytest
from dataclasses import replace

from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db
from betmodel.domain import FixtureRecord
from betmodel.free_data import sync_api_football
from betmodel.providers.api_football import ApiFootballOdds, ApiQuota


class FakeApiFootballClient:
    def __init__(self):
        self.odds_calls: list[str] = []

    def fetch_fixtures(self, date: str):
        fixtures = [
            FixtureRecord(
                source="api-football",
                provider_id="1",
                competition="Premier League",
                season="2026",
                kickoff=datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc),
                home_team="Arsenal",
                away_team="Chelsea",
            ),
            FixtureRecord(
                source="api-football",
                provider_id="2",
                competition="Premier League",
                season="2026",
                kickoff=datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc),
                home_team="Liverpool",
                away_team="Everton",
            ),
        ]
        return fixtures, ApiQuota(100, 3, 10, 9)

    def fetch_odds(self, fixture_id: str):
        self.odds_calls.append(fixture_id)
        odd = ApiFootballOdds(
            provider_fixture_id=fixture_id,
            competition="Premier League",
            season="2026",
            bookmaker="ExampleBook",
            market_name="Match Winner",
            selection="Home",
            decimal_odds=1.8,
            source_timestamp=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
        )
        return [odd], ApiQuota(100, 2, 10, 8)


def test_sync_api_football_stops_odds_calls_at_quota_reserve(tmp_path):
    settings = Settings(tmp_path)
    engine = create_engine_for(settings)
    init_db(engine)
    client = FakeApiFootballClient()

    result = sync_api_football(engine, client, "2026-09-20", quota_reserve=2,
                               now=datetime(2026,9,20,12,tzinfo=timezone.utc))

    assert client.odds_calls == ["1"]
    assert result.summary.fixtures == 2
    assert result.summary.odds_rows == 1
    assert result.odds_requests == 1
    assert result.quota.remaining == 2


def test_capped_sync_reports_unqueried_matches_and_empty_attempts(tmp_path):
    class EmptyClient(FakeApiFootballClient):
        def fetch_odds(self, fixture_id):
            return [], ApiQuota(100, 98, 10, 8)

    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    result = sync_api_football(engine, EmptyClient(), "2026-09-20", quota_reserve=0,
                              max_odds_requests=1, now=datetime(2026, 9, 20, 12, tzinfo=timezone.utc))
    assert result.pending_odds == 1
    assert result.attempted_fixture_ids == ["1"]
    assert result.summary.fixtures == 2
    assert result.odds_requests == 1
    assert result.quota.remaining == 98


@pytest.mark.parametrize("limited_by_header", [True, False])
def test_rate_limit_preserves_downloaded_fixtures_and_odds(tmp_path, limited_by_header):
    class LimitedClient(FakeApiFootballClient):
        def fetch_odds(self, fixture_id):
            if fixture_id == "2":
                response = httpx.Response(429, request=httpx.Request("GET", "https://example.com/odds"))
                response.raise_for_status()
            odds, _ = super().fetch_odds(fixture_id)
            return odds, ApiQuota(100, 98, 10, 0 if limited_by_header else 1)

    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    result = sync_api_football(engine, LimitedClient(), "2026-09-20", quota_reserve=0,
                               now=datetime(2026,9,20,12,tzinfo=timezone.utc))
    assert result.summary.fixtures == 2
    assert result.summary.odds_rows == 1
    assert result.rate_limited is True
    assert result.odds_requests == (1 if limited_by_header else 2)


def test_sync_does_not_swallow_other_http_errors(tmp_path):
    class BrokenClient(FakeApiFootballClient):
        def fetch_odds(self, fixture_id):
            httpx.Response(401, request=httpx.Request("GET", "https://example.com/odds")).raise_for_status()

    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    with pytest.raises(httpx.HTTPStatusError):
        sync_api_football(engine, BrokenClient(), "2026-09-20", quota_reserve=0,
                          now=datetime(2026,9,20,12,tzinfo=timezone.utc))


def test_sync_spends_odds_quota_only_on_upcoming_scheduled_matches(tmp_path):
    class MixedClient(FakeApiFootballClient):
        def fetch_fixtures(self, date):
            fixtures, quota = super().fetch_fixtures(date)
            base = fixtures[0]
            return [
                replace(base, provider_id="finished", status="FINISHED"),
                replace(base, provider_id="postponed", status="POSTPONED"),
                replace(base, provider_id="started", kickoff=datetime(2026, 9, 20, 10, tzinfo=timezone.utc)),
                replace(base, provider_id="later", kickoff=datetime(2026, 9, 20, 18, tzinfo=timezone.utc)),
                replace(base, provider_id="next", kickoff=datetime(2026, 9, 20, 13, tzinfo=timezone.utc)),
            ], quota

    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    client = MixedClient()
    result = sync_api_football(engine, client, "2026-09-20", quota_reserve=0, max_odds_requests=1,
                               now=datetime(2026, 9, 20, 12, tzinfo=timezone.utc))
    assert client.odds_calls == ["next"]
    assert result.summary.fixtures == 5
    assert result.summary.odds_rows == 1
