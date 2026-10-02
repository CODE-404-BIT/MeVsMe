from datetime import datetime

import httpx
import pytest

from betmodel.providers.openligadb import OpenLigaDBClient
from betmodel.providers.football_data_org import FootballDataOrgClient, MissingTokenError


def test_openligadb_maps_fixture_response():
    payload = [{
        "matchID": 42,
        "matchDateTimeUTC": "2026-09-20T14:00:00Z",
        "team1": {"teamName": "Arsenal"},
        "team2": {"teamName": "Chelsea"},
        "matchIsFinished": False,
    }]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = OpenLigaDBClient(http=httpx.Client(transport=transport))
    rows = client.fetch_matches("epl", "2026")
    assert rows[0].provider_id == "42"
    assert rows[0].home_team == "Arsenal"
    assert rows[0].kickoff == datetime.fromisoformat("2026-09-20T14:00:00+00:00")


def test_football_data_org_requires_token():
    with pytest.raises(MissingTokenError):
        FootballDataOrgClient(token=None).fetch_matches("PL", "2026-09-20", "2026-09-21")


def test_football_data_org_maps_fixture_response():
    payload = {"matches": [{
        "id": 99,
        "utcDate": "2026-09-20T16:30:00Z",
        "status": "SCHEDULED",
        "competition": {"code": "PL"},
        "season": {"startDate": "2026-08-01"},
        "homeTeam": {"name": "Liverpool FC"},
        "awayTeam": {"name": "Everton FC"},
    }]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = FootballDataOrgClient(token="free", http=httpx.Client(transport=transport))
    rows = client.fetch_matches("PL", "2026-09-20", "2026-09-21")
    assert rows[0].provider_id == "99"
    assert rows[0].home_team == "Liverpool FC"
    assert rows[0].season == "2026"
