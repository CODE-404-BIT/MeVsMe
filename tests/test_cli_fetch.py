from typer.testing import CliRunner

import betmodel.cli as cli
from betmodel.ingest import IngestSummary


def test_fetch_latest_command_uses_free_workflow(monkeypatch, tmp_path):
    called = {}

    def fake_fetch(engine, settings, season):
        called["season"] = season
        return IngestSummary(7, 14, 21)

    monkeypatch.setattr(cli, "fetch_latest_fixtures", fake_fetch, raising=False)
    result = CliRunner().invoke(cli.app, [
        "fetch-latest",
        "--season", "2026-27",
        "--root", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert called["season"] == "2026-27"
    assert "fixtures=7" in result.output


def test_fetch_season_command_uses_requested_league(monkeypatch, tmp_path):
    called = {}

    def fake_fetch(engine, settings, season_code, season, league_code):
        called.update(season_code=season_code, season=season, league_code=league_code)
        return IngestSummary(10, 20, 30)

    monkeypatch.setattr(cli, "fetch_season_league", fake_fetch, raising=False)
    result = CliRunner().invoke(cli.app, [
        "fetch-season",
        "--season-code", "2627",
        "--season", "2026-27",
        "--league", "E0",
        "--root", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert called == {"season_code": "2627", "season": "2026-27", "league_code": "E0"}
    assert "odds=30" in result.output
