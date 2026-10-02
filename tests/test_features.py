import pandas as pd
from betmodel.features import build_team_rolling_features


def test_rolling_features_exclude_current_and_future_matches():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-01-05", "2026-01-10"]),
        "team": ["A", "A", "A"],
        "goals": [1.0, 3.0, 10.0],
        "corners": [4.0, 6.0, 20.0],
    })
    out = build_team_rolling_features(frame, windows=(2,))
    assert pd.isna(out.loc[0, "goals_avg_2"])
    assert out.loc[1, "goals_avg_2"] == 1.0
    assert out.loc[2, "goals_avg_2"] == 2.0
    assert out.loc[2, "corners_avg_2"] == 5.0
