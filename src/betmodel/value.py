from __future__ import annotations

from collections.abc import Iterable


def _validate_probability(p: float) -> None:
    if not 0 < p < 1:
        raise ValueError("probability must be between 0 and 1")


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("decimal odds must be greater than 1")
    return 1.0 / decimal_odds


def devig(probabilities: Iterable[float]) -> list[float]:
    values = [float(p) for p in probabilities]
    if not values or any(p <= 0 for p in values):
        raise ValueError("probabilities must be positive")
    total = sum(values)
    if total <= 0:
        raise ValueError("probability total must be positive")
    return [p / total for p in values]


def expected_value(p: float, decimal_odds: float) -> float:
    _validate_probability(p)
    if decimal_odds <= 1:
        raise ValueError("decimal odds must be greater than 1")
    return p * decimal_odds - 1.0


def minimum_acceptable_odds(p: float, min_ev: float) -> float:
    _validate_probability(p)
    if min_ev < 0:
        raise ValueError("minimum EV cannot be negative")
    return (1.0 + min_ev) / p
