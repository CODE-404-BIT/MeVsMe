from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import numpy as np
import pandas as pd

from .calibration import brier_score


@dataclass(frozen=True)
class BacktestPrediction:
    fixture_date: pd.Timestamp
    training_max_date: pd.Timestamp
    probability: float
    outcome: int
    odds: float | None = None


@dataclass(frozen=True)
class BacktestReport:
    predictions: list[BacktestPrediction]
    brier_score: float
    log_loss: float
    hit_rate: float
    roi: float | None
    total_bets: int


def _binary_log_loss(probabilities: list[float], outcomes: list[int]) -> float:
    eps = 1e-12
    p = np.clip(np.asarray(probabilities, dtype=float), eps, 1 - eps)
    y = np.asarray(outcomes, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def walk_forward_backtest(
    matches: pd.DataFrame,
    train_min: int,
    predict_fn: Callable[[pd.DataFrame, pd.Series], dict],
) -> BacktestReport:
    if "date" not in matches.columns:
        raise ValueError("date column is required")
    if train_min < 1:
        raise ValueError("train_min must be at least 1")

    frame = matches.copy().sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"])
    if len(frame) <= train_min:
        raise ValueError("not enough rows for walk-forward backtest")

    predictions: list[BacktestPrediction] = []
    for idx in range(train_min, len(frame)):
        target = frame.iloc[idx]
        train = frame.iloc[:idx].copy()
        training_max_date = pd.Timestamp(train["date"].max())
        fixture_date = pd.Timestamp(target["date"])
        if not training_max_date < fixture_date:
            # Same-time duplicate fixtures would otherwise leak within-day results.
            train = frame[frame["date"] < fixture_date].copy()
            if len(train) < train_min:
                continue
            training_max_date = pd.Timestamp(train["date"].max())
        result = predict_fn(train, target)
        probability = float(result["probability"])
        outcome = int(result["outcome"])
        odds = result.get("odds")
        if not 0 <= probability <= 1:
            raise ValueError("predict_fn returned probability outside [0,1]")
        predictions.append(
            BacktestPrediction(
                fixture_date=fixture_date,
                training_max_date=training_max_date,
                probability=probability,
                outcome=outcome,
                odds=float(odds) if odds is not None else None,
            )
        )

    if not predictions:
        raise ValueError("no predictions produced")

    probs = [p.probability for p in predictions]
    outcomes = [p.outcome for p in predictions]
    hit_rate = float(np.mean([int((p.probability >= 0.5) == bool(p.outcome)) for p in predictions]))

    priced = [p for p in predictions if p.odds is not None]
    roi = None
    if priced:
        returns = [(p.odds - 1.0) if p.outcome else -1.0 for p in priced]
        roi = float(np.mean(returns))

    return BacktestReport(
        predictions=predictions,
        brier_score=brier_score(probs, outcomes),
        log_loss=_binary_log_loss(probs, outcomes),
        hit_rate=hit_rate,
        roi=roi,
        total_bets=len(predictions),
    )
