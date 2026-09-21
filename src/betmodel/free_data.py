from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import httpx

from sqlalchemy.engine import Engine

from .config import Settings
from .ingest import IngestSummary, ingest_api_football, ingest_football_data_uk
from .providers.api_football import ApiFootballClient, ApiQuota
from .providers.football_data_uk import download, latest_fixtures_url, season_csv_url

Downloader = Callable[[str, Path], Path]


def fetch_latest_fixtures(
    engine: Engine,
    settings: Settings,
    season: str,
    downloader: Downloader = download,
) -> IngestSummary:
    settings.ensure_directories()
    destination = settings.raw_dir / "football-data.co.uk" / "latest_fixtures.csv"
    downloader(latest_fixtures_url(), destination)
    return ingest_football_data_uk(engine, destination, competition="AUTO", season=season)


def fetch_season_league(
    engine: Engine,
    settings: Settings,
    season_code: str,
    season: str,
    league_code: str,
    downloader: Downloader = download,
) -> IngestSummary:
    settings.ensure_directories()
    destination = settings.raw_dir / "football-data.co.uk" / season_code / f"{league_code.upper()}.csv"
    downloader(season_csv_url(season_code, league_code), destination)
    return ingest_football_data_uk(engine, destination, competition=league_code.upper(), season=season)



@dataclass(frozen=True)
class ApiFootballSyncResult:
    summary: IngestSummary
    quota: ApiQuota
    odds_requests: int
    rate_limited: bool = False
    pending_odds: int = 0
    attempted_fixture_ids: list[str] = field(default_factory=list)


def sync_api_football(
    engine: Engine,
    client: ApiFootballClient,
    date: str,
    quota_reserve: int = 20,
    max_odds_requests: int = 20,
    now: datetime | None = None,
    fixture_priority: Callable | None = None,
) -> ApiFootballSyncResult:
    if quota_reserve < 0:
        raise ValueError("quota_reserve must be non-negative")
    if max_odds_requests < 0:
        raise ValueError("max_odds_requests must be non-negative")

    fixtures, quota = client.fetch_fixtures(date)
    odds_by_fixture: dict[str, list] = {}
    odds_requests = 0
    rate_limited = False
    attempted_fixture_ids = []

    run_now = now or datetime.now(timezone.utc)
    if run_now.tzinfo is None:
        run_now = run_now.replace(tzinfo=timezone.utc)

    def utc_kickoff(fixture):
        kickoff = fixture.kickoff
        return kickoff.replace(tzinfo=timezone.utc) if kickoff.tzinfo is None else kickoff.astimezone(timezone.utc)

    upcoming = sorted(
        (fixture for fixture in fixtures
         if fixture.status == "SCHEDULED" and utc_kickoff(fixture) > run_now),
        key=(lambda fixture: (fixture_priority(fixture), utc_kickoff(fixture))) if fixture_priority else utc_kickoff,
    )
    for fixture in upcoming:
        if odds_requests >= max_odds_requests:
            break
        if quota.remaining is not None and quota.remaining <= quota_reserve:
            break
        if quota.minute_remaining is not None and quota.minute_remaining <= 0:
            rate_limited = True
            break
        odds_requests += 1
        try:
            odds, quota = client.fetch_odds(fixture.provider_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            rate_limited = True
            break
        odds_by_fixture[fixture.provider_id] = odds
        attempted_fixture_ids.append(fixture.provider_id)

    summary = ingest_api_football(engine, fixtures, odds_by_fixture)
    return ApiFootballSyncResult(summary=summary, quota=quota, odds_requests=odds_requests, rate_limited=rate_limited,
                                 pending_odds=len(upcoming)-len(attempted_fixture_ids),
                                 attempted_fixture_ids=attempted_fixture_ids)
