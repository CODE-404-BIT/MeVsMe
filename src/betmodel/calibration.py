from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass
class IdentityCalibrator:
    def predict(self, probabilities: Iterable[float]) -> np.ndarray:
        values = np.asarray(list(probabilities), dtype=float)
        return np.clip(values, 0.0, 1.0)


@dataclass
class IsotonicCalibrator:
    model: IsotonicRegression

    def predict(self, probabilities: Iterable[float]) -> np.ndarray:
        values = np.asarray(list(probabilities), dtype=float)
        return np.clip(self.model.predict(values), 0.0, 1.0)


def brier_score(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    p = np.asarray(list(probabilities), dtype=float)
    y = np.asarray(list(outcomes), dtype=float)
    if len(p) != len(y) or len(p) == 0:
        raise ValueError("probabilities and outcomes must have equal non-zero length")
    return float(np.mean((p - y) ** 2))


def fit_isotonic_calibrator(
    probabilities: Iterable[float],
    outcomes: Iterable[int],
    min_samples: int = 30,
):
    p = np.asarray(list(probabilities), dtype=float)
    y = np.asarray(list(outcomes), dtype=float)
    if len(p) != len(y):
        raise ValueError("probabilities and outcomes length mismatch")
    if len(p) < min_samples or len(np.unique(y)) < 2:
        return IdentityCalibrator()
    model = IsotonicRegression(out_of_bounds="clip")
    model.fit(p, y)
    return IsotonicCalibrator(model)


def calibration_report(probabilities: Iterable[float], outcomes: Iterable[int]) -> dict[str, float]:
    return {"brier_score": brier_score(probabilities, outcomes)}
