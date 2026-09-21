from __future__ import annotations

import pandas as pd


DEFAULT_STATS = ("goals", "shots", "shots_on_target", "corners", "cards")


def build_team_rolling_features(
    matches: pd.DataFrame,
    windows: tuple[int, ...] = (5, 10, 20),
    stat_columns: tuple[str, ...] = DEFAULT_STATS,
) -> pd.DataFrame:
    required = {"date", "team"}
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    out = matches.copy().sort_values(["team", "date"]).reset_index(drop=True)
    for stat in stat_columns:
        if stat not in out.columns:
            continue
        shifted = out.groupby("team", sort=False)[stat].shift(1)
        for window in windows:
            out[f"{stat}_avg_{window}"] = (
                shifted.groupby(out["team"], sort=False)
                .rolling(window=window, min_periods=1)
                .mean()
                .reset_index(level=0, drop=True)
            )
    return out
