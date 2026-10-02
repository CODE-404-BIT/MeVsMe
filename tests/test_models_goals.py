import pandas as pd
import pytest

from betmodel.models_goals import fit_poisson_goal_model


def sample_history():
    return pd.DataFrame({
        "date": pd.to_datetime([
            "2026-01-01", "2026-01-02", "2026-01-08", "2026-01-09",
            "2026-01-15", "2026-01-16", "2026-01-22", "2026-01-23",
        ]),
        "home_team": ["A", "B", "A", "B", "A", "B", "A", "B"],
        "away_team": ["B", "A", "B", "A", "B", "A", "B", "A"],
        "home_goals": [3, 1, 2, 0, 4, 1, 3, 0],
        "away_goals": [0, 2, 1, 3, 0, 2, 1, 3],
    })


def test_score_matrix_is_probability_distribution():
    model = fit_poisson_goal_model(sample_history(), cutoff=pd.Timestamp("2026-02-01"))
    matrix = model.score_matrix("A", "B", max_goals=8)
    assert matrix.sum() == pytest.approx(1.0, abs=1e-9)
    assert matrix.shape == (9, 9)


def test_market_probabilities_are_coherent():
    model = fit_poisson_goal_model(sample_history(), cutoff=pd.Timestamp("2026-02-01"))
    probs = model.market_probabilities("A", "B")
    assert probs["MATCH_HOME"] > probs["MATCH_AWAY"]
    assert 0 < probs["TOTAL_GOALS_OVER_2_5"] < 1
    assert 0 < probs["BTTS_YES"] < 1
    assert probs["MATCH_HOME"] + probs["MATCH_DRAW"] + probs["MATCH_AWAY"] == pytest.approx(1.0)


def test_cutoff_excludes_future_matches():
    history = sample_history()
    future = pd.DataFrame({
        "date": pd.to_datetime(["2027-01-01"]),
        "home_team": ["B"], "away_team": ["A"], "home_goals": [20], "away_goals": [0]
    })
    expanded = pd.concat([history, future], ignore_index=True)
    base = fit_poisson_goal_model(history, cutoff=pd.Timestamp("2026-02-01"))
    with_future = fit_poisson_goal_model(expanded, cutoff=pd.Timestamp("2026-02-01"))
    assert with_future.expected_goals("A", "B") == pytest.approx(base.expected_goals("A", "B"))
