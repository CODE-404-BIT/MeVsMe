from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import pandas as pd
from scipy.stats import beta as beta_dist


@dataclass(frozen=True)
class PatternResult:
    row_index: int
    window: int
    hits: int
    trials: int
    raw_hit_rate: float
    posterior_mean: float
    lower_bound: float
    upper_bound: float


def beta_posterior_mean(hits: int, trials: int, alpha: float = 1.0, beta: float = 1.0) -> float:
    if trials < 0 or hits < 0 or hits > trials:
        raise ValueError("hits/trials are invalid")
    return (hits + alpha) / (trials + alpha + beta)


def beta_interval(
    hits: int,
    trials: int,
    alpha: float = 1.0,
    beta: float = 1.0,
    credibility: float = 0.95,
) -> tuple[float, float]:
    if not 0 < credibility < 1:
        raise ValueError("credibility must be between 0 and 1")
    a = hits + alpha
    b = trials - hits + beta
    tail = (1 - credibility) / 2
    return float(beta_dist.ppf(tail, a, b)), float(beta_dist.ppf(1 - tail, a, b))


def scan_patterns(
    frame: pd.DataFrame,
    market_fn: Callable[[pd.Series], bool],
    windows: Iterable[int] = (5, 10, 20),
) -> list[PatternResult]:
    if "date" not in frame.columns:
        raise ValueError("date column is required")
    ordered = frame.sort_values("date").reset_index(drop=True)
    outcomes = [bool(market_fn(row)) for _, row in ordered.iterrows()]
    results: list[PatternResult] = []
    for idx in range(len(ordered)):
        history = outcomes[:idx]
        for window in windows:
            if not history:
                continue
            sample = history[-window:]
            hits = sum(sample)
            trials = len(sample)
            low, high = beta_interval(hits, trials)
            results.append(
                PatternResult(
                    row_index=idx,
                    window=window,
                    hits=hits,
                    trials=trials,
                    raw_hit_rate=hits / trials,
                    posterior_mean=beta_posterior_mean(hits, trials),
                    lower_bound=low,
                    upper_bound=high,
                )
            )
    return results
