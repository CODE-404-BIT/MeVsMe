from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson


@dataclass(frozen=True)
class GoalModel:
    league_home_mean: float
    league_away_mean: float
    home_attack: dict[str, float]
    home_defence: dict[str, float]
    away_attack: dict[str, float]
    away_defence: dict[str, float]

    def expected_goals(self, home_team: str, away_team: str) -> tuple[float, float]:
        home_lambda = self.league_home_mean * self.home_attack.get(home_team, 1.0) * self.away_defence.get(away_team, 1.0)
        away_lambda = self.league_away_mean * self.away_attack.get(away_team, 1.0) * self.home_defence.get(home_team, 1.0)
        return max(home_lambda, 0.05), max(away_lambda, 0.05)

    def score_matrix(self, home_team: str, away_team: str, max_goals: int = 8) -> np.ndarray:
        home_lambda, away_lambda = self.expected_goals(home_team, away_team)
        goals = np.arange(max_goals + 1)
        matrix = np.outer(poisson.pmf(goals, home_lambda), poisson.pmf(goals, away_lambda))
        total = matrix.sum()
        return matrix / total if total else matrix

    def market_probabilities(self, home_team: str, away_team: str, max_goals: int = 10) -> dict[str, float]:
        matrix = self.score_matrix(home_team, away_team, max_goals=max_goals)
        home_win = float(np.tril(matrix, -1).sum())
        draw = float(np.trace(matrix))
        away_win = float(np.triu(matrix, 1).sum())
        over_25 = 0.0
        btts_yes = 0.0
        for h in range(matrix.shape[0]):
            for a in range(matrix.shape[1]):
                p = float(matrix[h, a])
                if h + a >= 3:
                    over_25 += p
                if h >= 1 and a >= 1:
                    btts_yes += p
        total_1x2 = home_win + draw + away_win
        if total_1x2:
            home_win, draw, away_win = (home_win / total_1x2, draw / total_1x2, away_win / total_1x2)
        return {
            "MATCH_HOME": home_win,
            "MATCH_DRAW": draw,
            "MATCH_AWAY": away_win,
            "TOTAL_GOALS_OVER_2_5": float(over_25),
            "TOTAL_GOALS_UNDER_2_5": float(1 - over_25),
            "BTTS_YES": float(btts_yes),
            "BTTS_NO": float(1 - btts_yes),
        }


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0 or np.isnan(numerator):
        return 1.0
    return max(0.25, min(4.0, numerator / denominator))


def fit_poisson_goal_model(history: pd.DataFrame, cutoff) -> GoalModel:
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[frame["date"] < pd.Timestamp(cutoff)]
    if frame.empty:
        raise ValueError("no historical matches before cutoff")

    league_home_mean = float(frame["home_goals"].mean())
    league_away_mean = float(frame["away_goals"].mean())
    if league_home_mean <= 0 or league_away_mean <= 0:
        raise ValueError("league goal means must be positive")

    teams = sorted(set(frame["home_team"]) | set(frame["away_team"]))
    home_attack: dict[str, float] = {}
    home_defence: dict[str, float] = {}
    away_attack: dict[str, float] = {}
    away_defence: dict[str, float] = {}

    for team in teams:
        home_rows = frame[frame["home_team"] == team]
        away_rows = frame[frame["away_team"] == team]
        home_attack[team] = _safe_ratio(float(home_rows["home_goals"].mean()), league_home_mean) if not home_rows.empty else 1.0
        home_defence[team] = _safe_ratio(float(home_rows["away_goals"].mean()), league_away_mean) if not home_rows.empty else 1.0
        away_attack[team] = _safe_ratio(float(away_rows["away_goals"].mean()), league_away_mean) if not away_rows.empty else 1.0
        away_defence[team] = _safe_ratio(float(away_rows["home_goals"].mean()), league_home_mean) if not away_rows.empty else 1.0

    return GoalModel(
        league_home_mean=league_home_mean,
        league_away_mean=league_away_mean,
        home_attack=home_attack,
        home_defence=home_defence,
        away_attack=away_attack,
        away_defence=away_defence,
    )
