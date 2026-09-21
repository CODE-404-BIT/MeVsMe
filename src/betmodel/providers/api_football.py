from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from betmodel.domain import FixtureRecord

SOURCE = "api-football"


class MissingApiFootballKey(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiQuota:
    limit: int | None
    remaining: int | None
    minute_limit: int | None
    minute_remaining: int | None


@dataclass(frozen=True)
class ApiFootballOdds:
    provider_fixture_id: str
    competition: str
    season: str
    bookmaker: str
    market_name: str
    selection: str
    decimal_odds: float
    source_timestamp: datetime | None


def _int_header(headers: httpx.Headers, name: str) -> int | None:
    raw = headers.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _quota(response: httpx.Response) -> ApiQuota:
    return ApiQuota(
        limit=_int_header(response.headers, "x-ratelimit-requests-limit"),
        remaining=_int_header(response.headers, "x-ratelimit-requests-remaining"),
        minute_limit=_int_header(response.headers, "x-ratelimit-limit"),
        minute_remaining=_int_header(response.headers, "x-ratelimit-remaining"),
    )


def _status(short: str | None) -> str:
    if short in {"FT", "AET", "PEN"}:
        return "FINISHED"
    if short in {"1H", "HT", "2H", "ET", "BT", "P", "INT", "LIVE"}:
        return "LIVE"
    if short in {"PST"}:
        return "POSTPONED"
    if short in {"CANC", "ABD", "AWD", "WO"}:
        return {"CANC": "CANCELLED", "ABD": "ABANDONED", "AWD": "AWARDED", "WO": "WALKOVER"}[short]
    return "SCHEDULED"


class ApiFootballClient:
    def __init__(
        self,
        api_key: str | None,
        http: httpx.Client | None = None,
        base_url: str = "https://v3.football.api-sports.io",
        checkpoint_engine=None,
    ):
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=20.0)
        self.base_url = base_url.rstrip("/")
        self.checkpoint_engine = checkpoint_engine

    def _get(self, path: str, params: dict[str, str]) -> httpx.Response:
        if not self.api_key:
            raise MissingApiFootballKey("API-FOOTBALL key is not configured")
        if self.checkpoint_engine is not None:
            from ..state_store import load_state, quota_key
            from datetime import timezone, timedelta
            saved=load_state(self.checkpoint_engine,quota_key(self.api_key))
            if saved:
                q=saved['quota']
                fresh=datetime.now(timezone.utc)-datetime.fromisoformat(saved['observed'])<timedelta(minutes=1)
                if (q.get('remaining') is not None and q['remaining']<=20) or (fresh and q.get('minute_remaining')==0):
                    raise RuntimeError('Provider request budget reached. Try again after the quota resets.')
        response = self.http.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"x-apisports-key": self.api_key},
        )
        if self.checkpoint_engine is not None:
            from ..state_store import save_state
            from dataclasses import asdict
            now=datetime.now(timezone.utc)
            save_state(self.checkpoint_engine,quota_key(self.api_key),{'quota':asdict(_quota(response)),'observed':now.isoformat()},
                (now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0))
        response.raise_for_status()
        payload = response.json()
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if errors:
            raise RuntimeError(f"API-FOOTBALL error: {errors}")
        return response

    def fetch_fixtures(self, date: str) -> tuple[list[FixtureRecord], ApiQuota]:
        response = self._get("/fixtures", {"date": date})
        rows: list[FixtureRecord] = []
        for item in response.json().get("response", []):
            fixture = item.get("fixture", {})
            kickoff_raw = fixture.get("date")
            if not kickoff_raw:
                continue
            league = item.get("league", {})
            teams = item.get("teams", {})
            rows.append(
                FixtureRecord(
                    source=SOURCE,
                    provider_id=str(fixture.get("id", "")),
                    competition=str(league.get("name") or league.get("id") or ""),
                    season=str(league.get("season") or ""),
                    kickoff=datetime.fromisoformat(str(kickoff_raw).replace("Z", "+00:00")),
                    home_team=str(teams.get("home", {}).get("name", "")),
                    away_team=str(teams.get("away", {}).get("name", "")),
                    status=_status(fixture.get("status", {}).get("short")),
                    league_id=str(league['id']) if league.get('id') is not None else None,
                    country=league.get('country'),
                )
            )
        return rows, _quota(response)

    def fetch_odds(self, fixture_id: str) -> tuple[list[ApiFootballOdds], ApiQuota]:
        response = self._get("/odds", {"fixture": str(fixture_id)})
        rows: list[ApiFootballOdds] = []
        for item in response.json().get("response", []):
            fixture = item.get("fixture", {})
            league = item.get("league", {})
            source_timestamp = None
            if item.get("update"):
                source_timestamp = datetime.fromisoformat(str(item["update"]).replace("Z", "+00:00"))
            provider_fixture_id = str(fixture.get("id") or fixture_id)
            for bookmaker in item.get("bookmakers", []):
                bookmaker_name = str(bookmaker.get("name", ""))
                for bet in bookmaker.get("bets", []):
                    market_name = str(bet.get("name", ""))
                    for value in bet.get("values", []):
                        try:
                            decimal_odds = float(value.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        if decimal_odds <= 1.0:
                            continue
                        rows.append(
                            ApiFootballOdds(
                                provider_fixture_id=provider_fixture_id,
                                competition=str(league.get("name") or league.get("id") or ""),
                                season=str(league.get("season") or ""),
                                bookmaker=bookmaker_name,
                                market_name=market_name,
                                selection=str(value.get("value", "")),
                                decimal_odds=decimal_odds,
                                source_timestamp=source_timestamp,
                            )
                        )
        return rows, _quota(response)
