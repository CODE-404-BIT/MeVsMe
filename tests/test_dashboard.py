from datetime import date, datetime, timezone
import pytest
from betmodel.dashboard import Dashboard, utc_window
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db
from test_daily_pipeline import seed_database as seed_unscoped_database


def seed_database(engine):
    from sqlalchemy import update
    from betmodel.models import Fixture
    seed_unscoped_database(engine)
    with engine.begin() as connection:
        connection.execute(update(Fixture).values(competition='E0'))


def test_local_day_spans_two_utc_dates():
    start, end = utc_window("2026-09-17", -600, -600)
    assert start == datetime(2026, 9, 16, 14, tzinfo=timezone.utc)
    assert end == datetime(2026, 9, 17, 14, tzinfo=timezone.utc)


def test_invalid_date_or_offset_is_rejected():
    with pytest.raises(ValueError):
        utc_window("oops", 0, 0)
    with pytest.raises(ValueError):
        utc_window("2026-09-17", 9000, 0)


def test_matches_include_coverage_and_do_not_leak_key(tmp_path):
    settings = Settings(tmp_path)
    engine = create_engine_for(settings)
    init_db(engine)
    seed_database(engine)
    app = Dashboard(tmp_path)
    app.set_key("  private-test-key  ")
    data = app.matches("2026-09-17", 0, 0)
    assert len(data["matches"]) == 5
    assert data["matches"][0]["history_home"] == 4
    assert data["matches"][0]["odds_count"] == 1
    assert data['matches'][0]['confidence'] is None
    assert 'confidence_reason' in data['matches'][0]
    assert "private-test-key" not in str(app.status())
    assert app.status()["key_configured"] is True


def test_analysis_rejects_small_unvalidated_history(tmp_path):
    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    seed_database(engine)
    app = Dashboard(tmp_path)
    app.analyze("2026-09-17", 0, 0, now=datetime(2026, 9, 17, 12, tzinfo=timezone.utc))
    page = app.combinations("2", 1, 2, False)
    assert page['total']==0 and page['items']==[]
    assert 'Suggestions do not require a model forecast or EV' in page['analysis']['reason']
