from datetime import datetime, timezone

from betmodel.candidates import Candidate
from betmodel.optimizer import Combination
from betmodel.reporting import DailyReport, render_daily_report

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def leg(fid, selection, odds, p):
    return Candidate(
        fixture_id=fid,
        fixture_key=f"F{fid}",
        market_key="TEST",
        selection=selection,
        decimal_odds=odds,
        model_probability=p,
        uncertainty=0.04,
        data_quality=0.90,
        pattern_strength=0.85,
        price_timestamp=NOW,
    )


def combo(*legs):
    odds = 1.0
    p = 1.0
    for x in legs:
        odds *= x.decimal_odds
        p *= x.model_probability
    ev = p * odds - 1
    return Combination(tuple(legs), odds, p, ev, ev)


def test_daily_report_renders_key_decision_information():
    two = combo(leg(1, "Arsenal 4+ corners", 1.40, 0.84), leg(2, "Over 1.5 goals", 1.45, 0.82))
    three = combo(leg(3, "Home +0.5", 1.50, 0.78), leg(4, "Over 1.5 goals", 1.42, 0.81), leg(5, "Away 3+ corners", 1.40, 0.82))
    report = DailyReport(
        report_date="2026-09-17",
        generated_at=NOW,
        best_2x=two,
        best_3x=three,
        scanned_matches=25,
        scanned_markets=320,
        valid_candidates=18,
    )
    rendered = render_daily_report(report)
    assert "BEST 2×" in rendered.text
    assert "BEST 3×" in rendered.text
    assert "Arsenal 4+ corners" in rendered.text
    assert "Minimum acceptable odds" in rendered.text
    assert "WHY SELECTED" in rendered.text
    assert "Leg EV" in rendered.text
    assert "25" in rendered.text
    assert "<html" in rendered.html.lower()
