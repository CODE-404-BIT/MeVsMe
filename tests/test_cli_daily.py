from datetime import date

from typer.testing import CliRunner

from betmodel.cli import app
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db
from tests.test_daily_pipeline import seed_database


def test_daily_cli_creates_preview(tmp_path):
    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    seed_database(engine)

    runner = CliRunner()
    result = runner.invoke(app, [
        "daily",
        "--date", "2026-09-17",
        "--root", str(tmp_path),
        "--preview-dir", str(tmp_path / "mail"),
        "--now", "2026-09-17T12:00:00+00:00",
    ])
    assert result.exit_code == 0, result.output
    assert "2x=" in result.output.lower()
    assert any((tmp_path / "mail").glob("*.html"))


def test_daily_cli_send_uses_free_smtp_configuration(monkeypatch, tmp_path):
    import betmodel.cli as cli

    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    seed_database(engine)
    sent = {}

    def fake_send(rendered, settings):
        sent["subject"] = rendered.subject
        sent["settings"] = settings

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SENDER", "sender@example.com")
    monkeypatch.setenv("SMTP_RECIPIENT", "me@example.com")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(cli, "send_smtp", fake_send, raising=False)

    result = CliRunner().invoke(cli.app, [
        "daily",
        "--date", "2026-09-17",
        "--root", str(tmp_path),
        "--preview-dir", str(tmp_path / "mail"),
        "--now", "2026-09-17T12:00:00+00:00",
        "--send",
    ])

    assert result.exit_code == 0, result.output
    assert sent["subject"] == "Daily Model Picks — 2026-09-17"
    assert sent["settings"].host == "smtp.gmail.com"
    assert sent["settings"].recipient == "me@example.com"
    assert "email=sent" in result.output


def test_daily_cli_send_fails_closed_when_smtp_is_missing(monkeypatch, tmp_path):
    import betmodel.cli as cli

    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    seed_database(engine)
    for name in ["SMTP_HOST", "SMTP_PORT", "SMTP_SENDER", "SMTP_RECIPIENT", "SMTP_USERNAME", "SMTP_PASSWORD"]:
        monkeypatch.delenv(name, raising=False)

    result = CliRunner().invoke(cli.app, [
        "daily",
        "--date", "2026-09-17",
        "--root", str(tmp_path),
        "--now", "2026-09-17T12:00:00+00:00",
        "--send",
    ])

    assert result.exit_code != 0
    assert "SMTP_HOST" in result.output
