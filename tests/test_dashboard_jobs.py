from datetime import datetime, timezone
import threading
import httpx
from betmodel.dashboard import Dashboard


def test_only_one_job_runs_and_failures_do_not_leak_credentials(tmp_path, monkeypatch):
    app = Dashboard(tmp_path)
    app.set_key("test-private-key")
    entered, release = threading.Event(), threading.Event()
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        raise RuntimeError("test-private-key in provider error")
    monkeypatch.setattr(app, "sync", blocked)
    assert app.start("sync", "2026-09-17", 0, 0)
    assert entered.wait(2)
    assert not app.start("analyze", "2026-09-17", 0, 0)
    release.set()
    app.worker.join(5)
    assert app.status()["job"]["state"] == "error"
    assert "test-private-key" not in str(app.status())


def test_rate_limit_is_shown_as_actionable_error(tmp_path, monkeypatch):
    app = Dashboard(tmp_path)
    app.set_key("test-key")
    def limited(*args):
        httpx.Response(429, request=httpx.Request("GET", "https://example.com")).raise_for_status()
    monkeypatch.setattr(app, "sync", limited)
    app.start("sync", "2026-09-17", 0, 0)
    app.worker.join(5)
    assert "rate limit" in app.status()["job"]["message"]


def test_empty_analysis_clears_previous_results(tmp_path):
    app = Dashboard(tmp_path)
    app.results["2"] = [{"ev": .2}]
    app.analyze("2026-09-17", 0, 0)
    assert app.combinations("2")["total"] == 0
    assert "historical" in app.status()["analysis"]["reason"]
