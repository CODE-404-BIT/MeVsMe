from __future__ import annotations

from datetime import datetime
import httpx

from betmodel.domain import FixtureRecord


class OpenLigaDBClient:
    def __init__(self, http: httpx.Client | None = None, base_url: str = "https://api.openligadb.de"):
        self.http = http or httpx.Client(timeout=20.0)
        self.base_url = base_url.rstrip("/")

    def fetch_matches(self, league_shortcut: str, season: str) -> list[FixtureRecord]:
        response = self.http.get(f"{self.base_url}/getmatchdata/{league_shortcut}/{season}")
        response.raise_for_status()
        rows: list[FixtureRecord] = []
        for item in response.json():
            kickoff_raw = item.get("matchDateTimeUTC") or item.get("matchDateTime")
            if not kickoff_raw:
                continue
            kickoff = datetime.fromisoformat(str(kickoff_raw).replace("Z", "+00:00"))
            rows.append(
                FixtureRecord(
                    source="openligadb",
                    provider_id=str(item.get("matchID", "")),
                    competition=league_shortcut,
                    season=str(season),
                    kickoff=kickoff,
                    home_team=item.get("team1", {}).get("teamName", ""),
                    away_team=item.get("team2", {}).get("teamName", ""),
                    status="FINISHED" if item.get("matchIsFinished") else "SCHEDULED",
                )
            )
        return rows
