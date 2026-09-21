from __future__ import annotations

from datetime import datetime
import httpx

from betmodel.domain import FixtureRecord


class MissingTokenError(RuntimeError):
    pass


class FootballDataOrgClient:
    def __init__(self, token: str | None, http: httpx.Client | None = None, base_url: str = "https://api.football-data.org/v4"):
        self.token = token
        self.http = http or httpx.Client(timeout=20.0)
        self.base_url = base_url.rstrip("/")

    def fetch_matches(self, competition_code: str, date_from: str, date_to: str) -> list[FixtureRecord]:
        if not self.token:
            raise MissingTokenError("football-data.org token is not configured")
        response = self.http.get(
            f"{self.base_url}/competitions/{competition_code}/matches",
            params={"dateFrom": date_from, "dateTo": date_to},
            headers={"X-Auth-Token": self.token},
        )
        response.raise_for_status()
        rows: list[FixtureRecord] = []
        for item in response.json().get("matches", []):
            kickoff = datetime.fromisoformat(item["utcDate"].replace("Z", "+00:00"))
            season_start = item.get("season", {}).get("startDate", "")
            rows.append(
                FixtureRecord(
                    source="football-data.org",
                    provider_id=str(item["id"]),
                    competition=item.get("competition", {}).get("code", competition_code),
                    season=season_start[:4] if season_start else "",
                    kickoff=kickoff,
                    home_team=item.get("homeTeam", {}).get("name", ""),
                    away_team=item.get("awayTeam", {}).get("name", ""),
                    status=item.get("status", "SCHEDULED"),
                )
            )
        return rows
