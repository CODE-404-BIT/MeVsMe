from __future__ import annotations

from pathlib import Path
import os
from datetime import date as date_type, datetime, timedelta, timezone
import typer

from .config import Settings
from .db import create_engine_for, init_db
from .ingest import ingest_football_data_uk
from .daily import run_daily_pipeline
from .emailer import SMTPSettings, send_smtp
from .reporting import render_daily_report
from .free_data import fetch_latest_fixtures, fetch_season_league, sync_api_football
from .providers.api_football import ApiFootballClient

app = typer.Typer(no_args_is_help=True)


@app.command("init-db")
def init_db_command(root: Path = typer.Option(Path("."), help="Project root")) -> None:
    settings = Settings(root.resolve())
    engine = create_engine_for(settings)
    init_db(engine)
    typer.echo(str(settings.database_path))


@app.command("ingest-football-data-uk")
def ingest_command(
    path: Path,
    competition: str = typer.Option(...),
    season: str = typer.Option(...),
    root: Path = typer.Option(Path(".")),
) -> None:
    settings = Settings(root.resolve())
    engine = create_engine_for(settings)
    init_db(engine)
    summary = ingest_football_data_uk(engine, path, competition, season)
    typer.echo(f"fixtures={summary.fixtures} stats={summary.team_stat_rows} odds={summary.odds_rows}")


@app.command("fetch-latest")
def fetch_latest_command(
    season: str = typer.Option(..., help="Season label, e.g. 2026-27"),
    root: Path = typer.Option(Path("."), help="Project root"),
) -> None:
    settings = Settings(root.resolve())
    engine = create_engine_for(settings)
    init_db(engine)
    summary = fetch_latest_fixtures(engine, settings, season)
    typer.echo(f"fixtures={summary.fixtures} stats={summary.team_stat_rows} odds={summary.odds_rows}")


@app.command("fetch-season")
def fetch_season_command(
    season_code: str = typer.Option(..., help="Archive season code, e.g. 2627"),
    season: str = typer.Option(..., help="Season label, e.g. 2026-27"),
    league: str = typer.Option(..., help="Football-Data.co.uk league code, e.g. E0"),
    root: Path = typer.Option(Path("."), help="Project root"),
) -> None:
    settings = Settings(root.resolve())
    engine = create_engine_for(settings)
    init_db(engine)
    summary = fetch_season_league(engine, settings, season_code, season, league)
    typer.echo(f"fixtures={summary.fixtures} stats={summary.team_stat_rows} odds={summary.odds_rows}")


@app.command("sync-api-football")
def sync_api_football_command(
    date: str = typer.Option(..., "--date", help="Fixture date YYYY-MM-DD"),
    root: Path = typer.Option(Path("."), help="Project root"),
    quota_reserve: int = typer.Option(20, min=0, max=99, help="Keep this many daily requests unused"),
) -> None:
    try:
        date_type.fromisoformat(date)
    except ValueError as exc:
        raise typer.BadParameter("date must be YYYY-MM-DD", param_hint="--date") from exc

    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        typer.echo("API_FOOTBALL_KEY is not configured; create a free API-FOOTBALL key and set the environment variable.", err=True)
        raise typer.Exit(code=2)

    settings = Settings(root.resolve())
    engine = create_engine_for(settings)
    init_db(engine)
    client = ApiFootballClient(api_key=api_key)
    result = sync_api_football(engine, client, date, quota_reserve)
    remaining = result.quota.remaining if result.quota.remaining is not None else "unknown"
    typer.echo(
        f"fixtures={result.summary.fixtures} odds={result.summary.odds_rows} "
        f"odds_requests={result.odds_requests} quota_remaining={remaining}"
    )
    if result.rate_limited:
        typer.echo("Rate limit reached; partial data saved. Wait for the provider's rate limit to reset before syncing again.")


@app.command("daily")
def daily_command(
    date: str = typer.Option(..., "--date", help="Report date YYYY-MM-DD"),
    root: Path = typer.Option(Path("."), help="Project root"),
    preview_dir: Path | None = typer.Option(None, help="Email preview output directory"),
    now: str | None = typer.Option(None, help="Override current UTC time for reproducible runs"),
    max_price_age_hours: int = typer.Option(72, min=1),
    send: bool = typer.Option(False, "--send", help="Send the report with free SMTP configuration"),
) -> None:
    settings = Settings(root.resolve())
    engine = create_engine_for(settings)
    init_db(engine)
    report_date = date_type.fromisoformat(date)
    run_now = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    if run_now.tzinfo is None:
        run_now = run_now.replace(tzinfo=timezone.utc)
    output_dir = (preview_dir or (settings.data_dir / "previews")).resolve()
    result = run_daily_pipeline(
        engine,
        report_date=report_date,
        now=run_now,
        preview_dir=output_dir,
        max_price_age=timedelta(hours=max_price_age_hours),
    )
    two = f"{result.report.best_2x.total_odds:.2f}" if result.report.best_2x else "none"
    three = f"{result.report.best_3x.total_odds:.2f}" if result.report.best_3x else "none"
    typer.echo(f"2x={two} 3x={three}")
    typer.echo(f"text={result.text_path}")
    typer.echo(f"html={result.html_path}")

    if send:
        required = ["SMTP_HOST", "SMTP_PORT", "SMTP_SENDER", "SMTP_RECIPIENT"]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            typer.echo(f"Missing SMTP configuration: {', '.join(missing)}", err=True)
            raise typer.Exit(code=2)
        try:
            port = int(os.environ["SMTP_PORT"])
        except ValueError as exc:
            typer.echo("SMTP_PORT must be an integer", err=True)
            raise typer.Exit(code=2) from exc
        tls_raw = os.getenv("SMTP_TLS", "true").strip().lower()
        smtp_settings = SMTPSettings(
            host=os.environ["SMTP_HOST"],
            port=port,
            sender=os.environ["SMTP_SENDER"],
            recipient=os.environ["SMTP_RECIPIENT"],
            username=os.getenv("SMTP_USERNAME") or None,
            password=os.getenv("SMTP_PASSWORD") or None,
            use_tls=tls_raw not in {"0", "false", "no", "off"},
        )
        rendered = render_daily_report(result.report)
        send_smtp(rendered, smtp_settings)
        typer.echo("email=sent")


if __name__ == "__main__":
    app()
