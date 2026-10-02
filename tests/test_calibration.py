import numpy as np
import pytest

from betmodel.calibration import brier_score, fit_isotonic_calibrator


def test_brier_score_matches_hand_calculation():
    probs = [0.8, 0.2]
    outcomes = [1, 0]
    assert brier_score(probs, outcomes) == pytest.approx(0.04)


def test_isotonic_calibrator_outputs_probabilities():
    probs = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9] * 5)
    outcomes = np.array([0, 0, 0, 1, 1, 1] * 5)
    calibrator = fit_isotonic_calibrator(probs, outcomes, min_samples=10)
    adjusted = calibrator.predict([0.15, 0.5, 0.85])
    assert all(0 <= p <= 1 for p in adjusted)
    assert adjusted[0] <= adjusted[1] <= adjusted[2]


def test_small_sample_uses_identity_calibration():
    calibrator = fit_isotonic_calibrator([0.3, 0.7], [0, 1], min_samples=10)
    assert list(calibrator.predict([0.25, 0.75])) == pytest.approx([0.25, 0.75])
