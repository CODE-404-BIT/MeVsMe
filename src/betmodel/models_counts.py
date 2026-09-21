from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd
from scipy.stats import nbinom, poisson


@dataclass(frozen=True)
class CountModel:
    stat_column: str
    distribution: str
    global_mean: float
    team_means: dict[str, float]
    dispersion: float | None = None

    def expected_count(self, context: dict) -> float:
        team = context.get("team")
        return max(0.01, float(self.team_means.get(team, self.global_mean)))

    def prob_over(self, line: float, context: dict) -> float:
        mean = self.expected_count(context)
        threshold = math.floor(line)
        if self.distribution == "negative_binomial" and self.dispersion:
            r = self.dispersion
            p = r / (r + mean)
            return float(1 - nbinom.cdf(threshold, r, p))
        return float(1 - poisson.cdf(threshold, mean))


def fit_count_model(
    history: pd.DataFrame,
    stat_column: str,
    cutoff,
    distribution: str = "poisson",
) -> CountModel:
    if stat_column not in history.columns:
        raise ValueError(f"missing stat column: {stat_column}")
    if "date" not in history.columns or "team" not in history.columns:
        raise ValueError("history requires date and team columns")

    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[frame["date"] < pd.Timestamp(cutoff)]
    values = pd.to_numeric(frame[stat_column], errors="coerce").dropna()
    if values.empty:
        raise ValueError(f"no valid values for {stat_column}")

    global_mean = float(values.mean())
    team_means = {
        str(team): float(pd.to_numeric(group[stat_column], errors="coerce").mean())
        for team, group in frame.groupby("team")
        if pd.notna(pd.to_numeric(group[stat_column], errors="coerce").mean())
    }

    if distribution not in {"poisson", "negative_binomial", "auto"}:
        raise ValueError("unsupported distribution")

    selected = distribution
    dispersion = None
    if distribution in {"negative_binomial", "auto"}:
        variance = float(values.var(ddof=1)) if len(values) > 1 else global_mean
        if variance > global_mean + 1e-9:
            dispersion = global_mean**2 / (variance - global_mean)
            selected = "negative_binomial"
        elif distribution == "negative_binomial":
            selected = "poisson"
        else:
            selected = "poisson"

    return CountModel(
        stat_column=stat_column,
        distribution=selected,
        global_mean=global_mean,
        team_means=team_means,
        dispersion=dispersion,
    )
