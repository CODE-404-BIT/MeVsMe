from datetime import datetime, timezone

import httpx
import pytest

from betmodel.providers.api_football import ApiFootballClient, MissingApiFootballKey


@pytest.mark.parametrize('short,expected', [('CANC', 'CANCELLED'), ('ABD', 'ABANDONED'), ('AWD', 'AWARDED'), ('WO', 'WALKOVER')])
def test_final_status_does_not_treat_abandoned_or_awarded_as_cancelled(short, expected):
    from betmodel.providers.api_football import _status
    assert _status(short) == expected


def test_api_football_requires_key():
    with pytest.raises(MissingApiFootballKey):
        ApiFootballClient(api_key=None).fetch_fixtures("2026-09-20")


def test_api_football_fetch_fixtures_maps_response_and_quota():
    payload = {
        "response": [
            {
                "fixture": {
                    "id": 123,
                    "date": "2026-09-20T14:00:00+00:00",
                    "status": {"short": "NS"},
                },
                "league": {"id": 39, "name": "Premier League", "season": 2026},
                "teams": {
                    "home": {"id": 42, "name": "Arsenal"},
                    "away": {"id": 49, "name": "Chelsea"},
                },
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fixtures"
        assert request.url.params["date"] == "2026-09-20"
        assert request.headers["x-apisports-key"] == "free-key"
        return httpx.Response(
            200,
            json=payload,
            headers={
                "x-ratelimit-requests-limit": "100",
                "x-ratelimit-requests-remaining": "87",
                "x-ratelimit-limit": "10",
                "x-ratelimit-remaining": "9",
            },
        )

    client = ApiFootballClient(
        api_key="free-key",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    fixtures, quota = client.fetch_fixtures("2026-09-20")

    assert len(fixtures) == 1
    assert fixtures[0].provider_id == "123"
    assert fixtures[0].competition == "Premier League"
    assert fixtures[0].season == "2026"
    assert fixtures[0].home_team == "Arsenal"
    assert fixtures[0].away_team == "Chelsea"
    assert fixtures[0].kickoff == datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)
    assert fixtures[0].status == "SCHEDULED"
    assert quota.limit == 100
    assert quota.remaining == 87
    assert quota.minute_limit == 10
    assert quota.minute_remaining == 9


def test_api_football_fetch_odds_flattens_bookmakers_and_tracks_update_time():
    payload = {
        "response": [
            {
                "league": {"id": 39, "name": "Premier League", "season": 2026},
                "fixture": {"id": 123},
                "update": "2026-09-20T12:30:00+00:00",
                "bookmakers": [
                    {
                        "id": 8,
                        "name": "ExampleBook",
                        "bets": [
                            {
                                "id": 1,
                                "name": "Match Winner",
                                "values": [
                                    {"value": "Home", "odd": "1.80"},
                                    {"value": "Draw", "odd": "3.60"},
                                    {"value": "Away", "odd": "4.50"},
                                ],
                            },
                            {
                                "id": 5,
                                "name": "Goals Over/Under",
                                "values": [
                                    {"value": "Over 2.5", "odd": "1.95"},
                                    {"value": "Under 2.5", "odd": "1.85"},
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=payload,
            headers={"x-ratelimit-requests-limit": "100", "x-ratelimit-requests-remaining": "70"},
        )
    )
    client = ApiFootballClient(api_key="free-key", http=httpx.Client(transport=transport))

    odds, quota = client.fetch_odds("123")

    assert len(odds) == 5
    home = odds[0]
    assert home.provider_fixture_id == "123"
    assert home.competition == "Premier League"
    assert home.season == "2026"
    assert home.bookmaker == "ExampleBook"
    assert home.market_name == "Match Winner"
    assert home.selection == "Home"
    assert home.decimal_odds == 1.80
    assert home.source_timestamp == datetime(2026, 9, 20, 12, 30, tzinfo=timezone.utc)
    assert quota.remaining == 70
