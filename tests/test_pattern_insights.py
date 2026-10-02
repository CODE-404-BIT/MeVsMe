from datetime import date

import pandas as pd

from betmodel.models import Fixture
from betmodel.pattern_insights import scan_fixture_patterns


def history_frame():
    rows = []
    for d in range(1, 7):
        rows.append({
            "date": pd.Timestamp(2026, 8, d),
            "home_team": "Strong",
            "away_team": f"X{d}",
            "home_goals": 2.0,
            "away_goals": 0.0,
            "home_corners": 6.0,
            "away_corners": 2.0,
            "home_shots": 14.0,
            "away_shots": 6.0,
            "home_sot": 5.0,
            "away_sot": 1.0,
            "home_cards": 1.0,
            "away_cards": 2.0,
        })
        rows.append({
            "date": pd.Timestamp(2026, 8, 10 + d),
            "home_team": f"Y{d}",
            "away_team": "Weak",
            "home_goals": 2.0,
            "away_goals": 0.0,
            "home_corners": 5.0,
            "away_corners": 2.0,
            "home_shots": 12.0,
            "away_shots": 6.0,
            "home_sot": 4.0,
            "away_sot": 1.0,
            "home_cards": 1.0,
            "away_cards": 2.0,
        })
    return pd.DataFrame(rows)


def test_scanner_finds_perfect_team_and_opponent_corner_patterns():
    fixture = Fixture(
        id=999,
        source="test",
        provider_id="target",
        competition="T",
        season="2026",
        match_date=date(2026, 9, 17),
        home_team="Strong",
        away_team="Weak",
        status="SCHEDULED",
    )
    insights = scan_fixture_patterns(history_frame(), fixture, windows=(5,), min_trials=5, min_raw_rate=0.8)
    labels = {i.label: i for i in insights}
    assert "Strong 4+ corners at home" in labels
    assert labels["Strong 4+ corners at home"].hits == 5
    assert labels["Strong 4+ corners at home"].raw_hit_rate == 1.0
    assert labels["Strong 4+ corners at home"].posterior_mean < 1.0
    assert "Weak conceded 4+ corners away" in labels


def test_scanner_only_uses_matches_before_target_date():
    frame = history_frame()
    future = frame.iloc[[0]].copy()
    future["date"] = pd.Timestamp("2026-10-01")
    future["home_corners"] = 0.0
    frame = pd.concat([frame, future], ignore_index=True)
    fixture = Fixture(
        id=999,
        source="test",
        provider_id="target",
        competition="T",
        season="2026",
        match_date=date(2026, 9, 17),
        home_team="Strong",
        away_team="Weak",
        status="SCHEDULED",
    )
    insights = scan_fixture_patterns(frame, fixture, windows=(5,), min_trials=5, min_raw_rate=0.8)
    corner = next(i for i in insights if i.label == "Strong 4+ corners at home")
    assert corner.raw_hit_rate == 1.0
