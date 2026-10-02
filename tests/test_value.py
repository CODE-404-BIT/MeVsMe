import pytest

from betmodel.value import devig, expected_value, implied_probability, minimum_acceptable_odds


def test_minimum_acceptable_odds_matches_hand_calculation():
    assert minimum_acceptable_odds(0.60, 0.05) == pytest.approx(1.75)


def test_expected_value_matches_hand_calculation():
    assert expected_value(0.58, 2.0) == pytest.approx(0.16)


def test_devig_normalizes_market_probabilities():
    raw = [implied_probability(1.70), implied_probability(4.00), implied_probability(5.50)]
    fair = devig(raw)
    assert sum(fair) == pytest.approx(1.0)
    assert all(0 < p < 1 for p in fair)


def test_invalid_decimal_odds_are_rejected():
    with pytest.raises(ValueError):
        implied_probability(1.0)
