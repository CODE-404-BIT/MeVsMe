from datetime import datetime, timezone
import pytest

from betmodel.candidates import Candidate
from betmodel.optimizer import Combination
from betmodel.settlement import performance_summary, settle_combination

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def leg(fid, name, odds):
    return Candidate(fid, f"F{fid}", "TEST", name, odds, 0.7, 0.05, 0.9, 0.8, NOW)


def make_combo():
    a, b = leg(1, "A", 1.5), leg(2, "B", 1.6)
    return Combination((a, b), 2.4, 0.49, 0.176, 0.176)


def test_winning_combination_returns_decimal_odds_minus_stake():
    settled = settle_combination(make_combo(), {"A": "win", "B": "win"})
    assert settled.status == "win"
    assert settled.return_multiple == pytest.approx(2.4)
    assert settled.profit == pytest.approx(1.4)


def test_void_leg_recalculates_return_multiple():
    settled = settle_combination(make_combo(), {"A": "win", "B": "void"})
    assert settled.status == "win"
    assert settled.return_multiple == pytest.approx(1.5)


def test_any_loss_loses_combination():
    settled = settle_combination(make_combo(), {"A": "win", "B": "loss"})
    assert settled.status == "loss"
    assert settled.profit == -1.0


def test_performance_summary_reports_roi_and_hit_rate():
    settlements = [
        settle_combination(make_combo(), {"A": "win", "B": "win"}),
        settle_combination(make_combo(), {"A": "win", "B": "loss"}),
    ]
    summary = performance_summary(settlements)
    assert summary["bets"] == 2
    assert summary["hit_rate"] == pytest.approx(0.5)
    assert summary["roi"] == pytest.approx(0.2)
