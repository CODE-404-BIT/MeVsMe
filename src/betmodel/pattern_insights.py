from __future__ import annotations

from dataclasses import dataclass
from math import log1p
from typing import Iterable

import pandas as pd

from .models import Fixture
from .patterns import beta_interval, beta_posterior_mean


@dataclass(frozen=True)
class PatternInsight:
    fixture_id: int
    fixture_key: str
    category: str
    label: str
    window: int
    hits: int
    trials: int
    raw_hit_rate: float
    posterior_mean: float
    lower_bound: float
    upper_bound: float
    score: float


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _add_pattern(
    output: list[PatternInsight],
    fixture: Fixture,
    label: str,
    category: str,
    outcomes: pd.Series,
    windows: Iterable[int],
    min_trials: int,
    min_raw_rate: float,
) -> None:
    clean = outcomes.dropna().astype(bool)
    for window in windows:
        sample = clean.tail(window)
        trials = len(sample)
        if trials < min_trials:
            continue
        hits = int(sample.sum())
        raw = hits / trials
        if raw < min_raw_rate:
            continue
        posterior = beta_posterior_mean(hits, trials)
        low, high = beta_interval(hits, trials)
        # Lower bound rewards reliability while log sample size rewards durable patterns.
        score = float(low + 0.025 * log1p(trials))
        output.append(
            PatternInsight(
                fixture_id=fixture.id,
                fixture_key=f"{fixture.home_team} v {fixture.away_team}",
                category=category,
                label=label,
                window=window,
                hits=hits,
                trials=trials,
                raw_hit_rate=raw,
                posterior_mean=posterior,
                lower_bound=low,
                upper_bound=high,
                score=score,
            )
        )


def _team_own_patterns(
    output: list[PatternInsight],
    fixture: Fixture,
    frame: pd.DataFrame,
    team: str,
    venue: str,
    prefix: str,
    windows: Iterable[int],
    min_trials: int,
    min_raw_rate: float,
) -> None:
    if venue == "home":
        subset = frame[frame["home_team"] == team].sort_values("date")
        goals, corners, shots, sot, cards = "home_goals", "home_corners", "home_shots", "home_sot", "home_cards"
        venue_text = "at home"
    else:
        subset = frame[frame["away_team"] == team].sort_values("date")
        goals, corners, shots, sot, cards = "away_goals", "away_corners", "away_shots", "away_sot", "away_cards"
        venue_text = "away"

    definitions = [
        ("goals", goals, 1, f"{prefix} 1+ goals {venue_text}"),
        ("goals", goals, 2, f"{prefix} 2+ goals {venue_text}"),
        ("corners", corners, 3, f"{prefix} 3+ corners {venue_text}"),
        ("corners", corners, 4, f"{prefix} 4+ corners {venue_text}"),
        ("corners", corners, 5, f"{prefix} 5+ corners {venue_text}"),
        ("shots", shots, 8, f"{prefix} 8+ shots {venue_text}"),
        ("shots", shots, 10, f"{prefix} 10+ shots {venue_text}"),
        ("sot", sot, 1, f"{prefix} 1+ SOT {venue_text}"),
        ("sot", sot, 2, f"{prefix} 2+ SOT {venue_text}"),
        ("sot", sot, 3, f"{prefix} 3+ SOT {venue_text}"),
        ("cards", cards, 1, f"{prefix} 1+ cards {venue_text}"),
        ("cards", cards, 2, f"{prefix} 2+ cards {venue_text}"),
    ]
    for category, column, threshold, label in definitions:
        values = _numeric(subset, column)
        _add_pattern(output, fixture, label, category, values >= threshold, windows, min_trials, min_raw_rate)


def _conceded_patterns(
    output: list[PatternInsight],
    fixture: Fixture,
    frame: pd.DataFrame,
    defending_team: str,
    venue: str,
    windows: Iterable[int],
    min_trials: int,
    min_raw_rate: float,
) -> None:
    if venue == "away":
        subset = frame[frame["away_team"] == defending_team].sort_values("date")
        venue_text = "away"
        columns = {
            "goals": "home_goals",
            "corners": "home_corners",
            "shots": "home_shots",
            "sot": "home_sot",
        }
    else:
        subset = frame[frame["home_team"] == defending_team].sort_values("date")
        venue_text = "at home"
        columns = {
            "goals": "away_goals",
            "corners": "away_corners",
            "shots": "away_shots",
            "sot": "away_sot",
        }

    definitions = [
        ("goals", 1), ("goals", 2),
        ("corners", 3), ("corners", 4), ("corners", 5),
        ("shots", 8), ("shots", 10),
        ("sot", 1), ("sot", 2), ("sot", 3),
    ]
    for category, threshold in definitions:
        column = columns[category]
        unit = "SOT" if category == "sot" else category
        label = f"{defending_team} conceded {threshold}+ {unit} {venue_text}"
        values = _numeric(subset, column)
        _add_pattern(output, fixture, label, f"conceded_{category}", values >= threshold, windows, min_trials, min_raw_rate)


def _match_patterns(
    output: list[PatternInsight],
    fixture: Fixture,
    subset: pd.DataFrame,
    prefix: str,
    windows: Iterable[int],
    min_trials: int,
    min_raw_rate: float,
) -> None:
    subset = subset.sort_values("date")
    total_goals = _numeric(subset, "home_goals") + _numeric(subset, "away_goals")
    total_corners = _numeric(subset, "home_corners") + _numeric(subset, "away_corners")
    btts = (_numeric(subset, "home_goals") >= 1) & (_numeric(subset, "away_goals") >= 1)
    definitions = [
        ("match_goals", f"{prefix}: over 1.5 goals", total_goals > 1.5),
        ("match_goals", f"{prefix}: over 2.5 goals", total_goals > 2.5),
        ("btts", f"{prefix}: BTTS", btts),
        ("match_corners", f"{prefix}: over 6.5 corners", total_corners > 6.5),
        ("match_corners", f"{prefix}: over 8.5 corners", total_corners > 8.5),
    ]
    for category, label, outcomes in definitions:
        _add_pattern(output, fixture, label, category, outcomes, windows, min_trials, min_raw_rate)


def scan_fixture_patterns(
    history: pd.DataFrame,
    fixture: Fixture,
    windows: Iterable[int] = (5, 10, 20),
    min_trials: int = 5,
    min_raw_rate: float = 0.80,
) -> list[PatternInsight]:
    if fixture.match_date is None:
        return []
    if history.empty:
        return []
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[frame["date"] < pd.Timestamp(fixture.match_date)]
    if frame.empty:
        return []

    output: list[PatternInsight] = []
    _team_own_patterns(output, fixture, frame, fixture.home_team, "home", fixture.home_team, windows, min_trials, min_raw_rate)
    _team_own_patterns(output, fixture, frame, fixture.away_team, "away", fixture.away_team, windows, min_trials, min_raw_rate)
    _conceded_patterns(output, fixture, frame, fixture.away_team, "away", windows, min_trials, min_raw_rate)
    _conceded_patterns(output, fixture, frame, fixture.home_team, "home", windows, min_trials, min_raw_rate)

    home_recent = frame[frame["home_team"] == fixture.home_team]
    away_recent = frame[frame["away_team"] == fixture.away_team]
    _match_patterns(output, fixture, home_recent, f"{fixture.home_team} home matches", windows, min_trials, min_raw_rate)
    _match_patterns(output, fixture, away_recent, f"{fixture.away_team} away matches", windows, min_trials, min_raw_rate)

    h2h = frame[
        ((frame["home_team"] == fixture.home_team) & (frame["away_team"] == fixture.away_team))
        | ((frame["home_team"] == fixture.away_team) & (frame["away_team"] == fixture.home_team))
    ]
    _match_patterns(output, fixture, h2h, "H2H", windows, min_trials, min_raw_rate)

    # Keep the strongest window for each semantic label so email output stays concise.
    best: dict[str, PatternInsight] = {}
    for insight in output:
        existing = best.get(insight.label)
        if existing is None or (insight.score, insight.trials) > (existing.score, existing.trials):
            best[insight.label] = insight
    return sorted(best.values(), key=lambda x: (x.score, x.raw_hit_rate, x.trials), reverse=True)
