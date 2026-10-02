from datetime import datetime, timezone

from betmodel.candidates import Candidate
from betmodel.optimizer import optimize_combinations

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def c(fid, name, odds, p, uncertainty=0.03, quality=0.95):
    return Candidate(
        fixture_id=fid,
        fixture_key=f"fixture-{fid}",
        market_key="TEST",
        selection=name,
        decimal_odds=odds,
        model_probability=p,
        uncertainty=uncertainty,
        data_quality=quality,
        pattern_strength=0.8,
        price_timestamp=NOW,
    )


def test_optimizer_prefers_expected_value_not_highest_total_odds():
    candidates = [
        c(1, "A", 1.40, 0.85),
        c(2, "B", 1.45, 0.82),
        c(3, "C", 1.50, 0.70),
        c(4, "D", 1.50, 0.69),
    ]
    combos = optimize_combinations(candidates, 1.80, 2.30, max_legs=2)
    assert combos
    best = combos[0]
    assert {leg.selection for leg in best.legs} == {"A", "B"}
    assert 1.80 <= best.total_odds <= 2.30


def test_optimizer_rejects_same_fixture_legs():
    candidates = [
        c(1, "A", 1.50, 0.80),
        c(1, "B", 1.40, 0.85),
        c(2, "C", 1.40, 0.80),
    ]
    combos = optimize_combinations(candidates, 1.80, 2.30, max_legs=2)
    assert all(len({leg.fixture_id for leg in combo.legs}) == len(combo.legs) for combo in combos)


def test_optimizer_tracks_safety_rating_and_allows_wider_odds_window():
    candidates = [
        c(1, "A", 1.90, 0.82),
        c(2, "B", 2.10, 0.74),
        c(3, "C", 2.40, 0.68),
        c(4, "D", 3.20, 0.52),
    ]
    combos = optimize_combinations(candidates, 1.00, 25.00, max_legs=3)
    assert combos
    assert all(0.0 <= combo.safety_rating <= 10.0 for combo in combos)
    assert max(combo.safety_rating for combo in combos) > 0
