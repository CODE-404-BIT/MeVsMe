from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import prod

from .candidates import Candidate


@dataclass(frozen=True)
class Combination:
    legs: tuple[Candidate, ...]
    total_odds: float
    joint_probability: float
    expected_value: float
    score: float = 0.0
    safety_rating: float = 0.0


def _safety_rating(legs: tuple[Candidate, ...], total_odds: float, joint_probability: float) -> float:
    avg_quality = sum(leg.data_quality for leg in legs) / len(legs)
    avg_uncertainty = sum(leg.uncertainty for leg in legs) / len(legs)
    avg_pattern = sum(leg.pattern_strength for leg in legs) / len(legs)
    stability = max(0.0, 1.0 - avg_uncertainty)
    prob_edge = max(0.0, (joint_probability * total_odds - 1.0) / max(total_odds - 1.0, 0.01))
    rating = (0.35 * avg_quality + 0.30 * stability + 0.20 * avg_pattern + 0.15 * prob_edge) * 10.0
    return max(0.0, min(10.0, rating))


def _score_combo(legs: tuple[Candidate, ...], total_odds: float, joint_probability: float) -> float:
    ev = joint_probability * total_odds - 1.0
    avg_quality = sum(leg.data_quality for leg in legs) / len(legs)
    avg_uncertainty = sum(leg.uncertainty for leg in legs) / len(legs)
    avg_pattern = sum(leg.pattern_strength for leg in legs) / len(legs)
    stability = max(0.0, 1.0 - avg_uncertainty)
    safety = _safety_rating(legs, total_odds, joint_probability) / 10.0
    return ev * avg_quality * stability * (0.75 + 0.25 * avg_pattern) * (0.6 + 0.4 * safety)


def optimize_combinations(
    candidates: list[Candidate],
    min_odds: float,
    max_odds: float,
    max_legs: int = 4,
) -> list[Combination]:
    if min_odds <= 0 or max_odds <= min_odds:
        raise ValueError("invalid target odds range")
    if max_legs < 2:
        raise ValueError("max_legs must be at least 2")

    results: list[Combination] = []
    for size in range(2, min(max_legs, len(candidates)) + 1):
        for legs in combinations(candidates, size):
            fixture_ids = [leg.fixture_id for leg in legs]
            if len(set(fixture_ids)) != len(fixture_ids):
                continue
            if len({leg.bookmaker for leg in legs}) != 1:
                continue
            total_odds = prod(leg.decimal_odds for leg in legs)
            if not min_odds <= total_odds <= max_odds:
                continue
            joint_probability = prod(leg.model_probability for leg in legs)
            ev = joint_probability * total_odds - 1.0
            safety = _safety_rating(legs, total_odds, joint_probability)
            results.append(
                Combination(
                    legs=legs,
                    total_odds=total_odds,
                    joint_probability=joint_probability,
                    expected_value=ev,
                    score=_score_combo(legs, total_odds, joint_probability),
                    safety_rating=safety,
                )
            )
    return sorted(results, key=lambda combo: (combo.score, combo.expected_value, combo.safety_rating), reverse=True)
