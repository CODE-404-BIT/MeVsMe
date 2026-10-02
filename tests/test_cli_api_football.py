from typer.testing import CliRunner

import betmodel.cli as cli
from betmodel.free_data import ApiFootballSyncResult
from betmodel.ingest import IngestSummary
from betmodel.providers.api_football import ApiQuota


def test_sync_api_football_cli_uses_free_key_and_prints_quota(monkeypatch, tmp_path):
    called = {}

    class FakeClient:
        def __init__(self, api_key):
            called["key"] = api_key

    def fake_sync(engine, client, date, quota_reserve):
        called.update(date=date, reserve=quota_reserve)
        return ApiFootballSyncResult(
            summary=IngestSummary(fixtures=8, team_stat_rows=0, odds_rows=14),
            quota=ApiQuota(limit=100, remaining=71, minute_limit=10, minute_remaining=8),
            odds_requests=8,
        )

    monkeypatch.setenv("API_FOOTBALL_KEY", "free-key")
    monkeypatch.setattr(cli, "ApiFootballClient", FakeClient, raising=False)
    monkeypatch.setattr(cli, "sync_api_football", fake_sync, raising=False)

    result = CliRunner().invoke(
        cli.app,
        [
            "sync-api-football",
            "--date", "2026-09-20",
            "--root", str(tmp_path),
            "--quota-reserve", "20",
        ],
    )

    assert result.exit_code == 0, result.output
    assert called == {"key": "free-key", "date": "2026-09-20", "reserve": 20}
    assert "fixtures=8" in result.output
    assert "odds=14" in result.output
    assert "quota_remaining=71" in result.output


def test_sync_api_football_cli_fails_cleanly_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    result = CliRunner().invoke(
        cli.app,
        ["sync-api-football", "--date", "2026-09-20", "--root", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "API_FOOTBALL_KEY" in result.output
