from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from math import floor, sqrt
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from scipy.stats import poisson
from sqlalchemy import select
from sqlalchemy.engine import Engine

from .candidates import Candidate, quality_grade, validate_candidate
from .db import session_factory
from .emailer import save_preview
from .models import (
    Fixture,
    ModelVersion,
    OddsSnapshot,
    Prediction,
    Recommendation,
    RecommendationLeg,
    TeamMatchStat,
    ProviderMapping,
)
from .models_goals import fit_poisson_goal_model
from .optimizer import Combination, optimize_combinations
from .patterns import beta_posterior_mean
from .reporting import DailyReport, render_daily_report


@dataclass(frozen=True)
class DailyRunResult:
    report: DailyReport
    text_path: Path
    html_path: Path
    combinations_2x: list[Combination] = field(default_factory=list)
    combinations_3x: list[Combination] = field(default_factory=list)
    search_candidates: int = 0


def _utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _history_dataframe(session, report_date: date) -> pd.DataFrame:
    fixtures = session.scalars(
        select(Fixture).where(Fixture.status == "FINISHED", Fixture.match_date < report_date)
    ).all()
    rows: list[dict] = []
    for fixture in fixtures:
        stats = session.scalars(
            select(TeamMatchStat).where(TeamMatchStat.fixture_id == fixture.id)
        ).all()
        home = next((s for s in stats if s.is_home == 1), None)
        away = next((s for s in stats if s.is_home == 0), None)
        if not home or not away or home.goals is None or away.goals is None:
            continue
        rows.append(
            {
                "date": pd.Timestamp(fixture.match_date),
                "fixture_id": fixture.id,
                "competition": fixture.competition,
                "home_team": fixture.home_team,
                "away_team": fixture.away_team,
                "home_goals": float(home.goals),
                "away_goals": float(away.goals),
                "home_corners": home.corners,
                "away_corners": away.corners,
                "home_shots": home.shots,
                "away_shots": away.shots,
                "home_sot": home.shots_on_target,
                "away_sot": away.shots_on_target,
                "home_cards": home.cards,
                "away_cards": away.cards,
            }
        )
    return pd.DataFrame(rows)


def _team_sample_count(history: pd.DataFrame, team: str) -> int:
    if history.empty:
        return 0
    return int(((history["home_team"] == team) | (history["away_team"] == team)).sum())


def _pattern_strength(history: pd.DataFrame, fixture: Fixture, market_key: str, line: float | None) -> float:
    if history.empty:
        return 0.5
    team_history = history[
        (history["home_team"] == fixture.home_team) | (history["away_team"] == fixture.home_team)
    ].sort_values("date").tail(20)
    if team_history.empty:
        return 0.5

    if market_key == "MATCH_HOME":
        relevant = team_history[team_history["home_team"] == fixture.home_team]
        outcomes = relevant["home_goals"] > relevant["away_goals"]
    elif market_key == "MATCH_DRAW":
        outcomes = team_history["home_goals"] == team_history["away_goals"]
    elif market_key == "MATCH_AWAY":
        relevant = history[history["away_team"] == fixture.away_team].sort_values("date").tail(20)
        outcomes = relevant["away_goals"] > relevant["home_goals"]
    elif market_key in {"TOTAL_GOALS_OVER", "TOTAL_GOALS_UNDER"}:
        threshold = float(line if line is not None else 2.5)
        totals = team_history["home_goals"] + team_history["away_goals"]
        if market_key.endswith("OVER"):
            outcomes = totals > threshold
        else:
            outcomes = totals < threshold
    else:
        return 0.5

    trials = int(len(outcomes))
    hits = int(outcomes.sum()) if trials else 0
    return beta_posterior_mean(hits, trials) if trials else 0.5


def _goal_market_probability(probs: dict[str, float], odds: OddsSnapshot) -> float | None:
    mapping = {
        "MATCH_HOME": "MATCH_HOME",
        "MATCH_DRAW": "MATCH_DRAW",
        "MATCH_AWAY": "MATCH_AWAY",
        "TOTAL_GOALS_OVER": "TOTAL_GOALS_OVER_2_5",
        "TOTAL_GOALS_UNDER": "TOTAL_GOALS_UNDER_2_5",
        "BTTS_YES": "BTTS_YES",
        "BTTS_NO": "BTTS_NO",
    }
    key = mapping.get(odds.market_key)
    if key is None:
        return None
    if odds.market_key.startswith("TOTAL_GOALS") and odds.line not in {None, 2.5}:
        return None
    return probs.get(key)


def _clean_stat(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _team_stat_projection(
    history: pd.DataFrame,
    fixture: Fixture,
    stat: str,
    is_home_team: bool,
    min_samples: int = 3,
) -> tuple[float, int] | None:
    home_col = f"home_{stat}"
    away_col = f"away_{stat}"
    if home_col not in history.columns or away_col not in history.columns:
        return None

    if is_home_team:
        own_rows = history[history["home_team"] == fixture.home_team].sort_values("date").tail(20)
        opponent_rows = history[history["away_team"] == fixture.away_team].sort_values("date").tail(20)
        own = _clean_stat(own_rows, home_col)
        opponent_conceded = _clean_stat(opponent_rows, home_col)
    else:
        own_rows = history[history["away_team"] == fixture.away_team].sort_values("date").tail(20)
        opponent_rows = history[history["home_team"] == fixture.home_team].sort_values("date").tail(20)
        own = _clean_stat(own_rows, away_col)
        opponent_conceded = _clean_stat(opponent_rows, away_col)

    if len(own) < min_samples or len(opponent_conceded) < min_samples:
        return None
    projected = (float(own.mean()) + float(opponent_conceded.mean())) / 2.0
    return max(0.01, projected), min(len(own), len(opponent_conceded))


def _count_market_definition(market_key: str) -> tuple[str, bool, bool] | None:
    definitions = {
        "TOTAL_CORNERS_OVER": ("corners", True, True),
        "TOTAL_CORNERS_UNDER": ("corners", True, False),
        "TEAM_CORNERS_OVER": ("corners", False, True),
        "TEAM_CORNERS_UNDER": ("corners", False, False),
        "TOTAL_CARDS_OVER": ("cards", True, True),
        "TOTAL_CARDS_UNDER": ("cards", True, False),
        "TEAM_CARDS_OVER": ("cards", False, True),
        "TEAM_CARDS_UNDER": ("cards", False, False),
        "TEAM_SHOTS_OVER": ("shots", False, True),
        "TEAM_SHOTS_UNDER": ("shots", False, False),
        "TEAM_SOT_OVER": ("sot", False, True),
        "TEAM_SOT_UNDER": ("sot", False, False),
    }
    return definitions.get(market_key)


def _team_side_from_selection(fixture: Fixture, selection: str) -> bool | None:
    import re
    from .team_insights import team_key
    team = team_key(re.split(r'\s+(?:over|under)\b', selection, maxsplit=1, flags=re.I)[0])
    if team == team_key(fixture.home_team):
        return True
    if team == team_key(fixture.away_team):
        return False
    return None


def _prob_from_poisson(mean: float, line: float, is_over: bool) -> float:
    # Whole-number Asian lines can push; V1 only prices non-integer totals to avoid
    # pretending a two-way win/loss probability when a push is possible.
    if abs(line - round(line)) < 1e-9:
        raise ValueError("integer count lines with push outcomes are unsupported")
    threshold = floor(line)
    if is_over:
        return float(1.0 - poisson.cdf(threshold, mean))
    return float(poisson.cdf(threshold, mean))


def _count_market_probability(
    history: pd.DataFrame,
    fixture: Fixture,
    odds: OddsSnapshot,
) -> tuple[float, int] | None:
    definition = _count_market_definition(odds.market_key)
    if definition is None or odds.line is None:
        return None
    stat, is_total, is_over = definition

    if is_total:
        home_projection = _team_stat_projection(history, fixture, stat, True)
        away_projection = _team_stat_projection(history, fixture, stat, False)
        if home_projection is None or away_projection is None:
            return None
        mean = home_projection[0] + away_projection[0]
        sample_n = min(home_projection[1], away_projection[1])
    else:
        side = _team_side_from_selection(fixture, odds.selection)
        if side is None:
            return None
        projection = _team_stat_projection(history, fixture, stat, side)
        if projection is None:
            return None
        mean, sample_n = projection

    try:
        probability = _prob_from_poisson(mean, float(odds.line), is_over)
    except ValueError:
        return None
    if not 0 < probability < 1:
        return None
    return probability, sample_n


def _count_pattern_strength(
    history: pd.DataFrame,
    fixture: Fixture,
    odds: OddsSnapshot,
) -> float:
    definition = _count_market_definition(odds.market_key)
    if definition is None or odds.line is None:
        return 0.5
    stat, is_total, is_over = definition
    home_col = f"home_{stat}"
    away_col = f"away_{stat}"
    line = float(odds.line)

    if is_total:
        home_recent = history[history["home_team"] == fixture.home_team].sort_values("date").tail(20)
        away_recent = history[history["away_team"] == fixture.away_team].sort_values("date").tail(20)
        home_totals = _clean_stat(home_recent, home_col) + _clean_stat(home_recent, away_col)
        away_totals = _clean_stat(away_recent, home_col) + _clean_stat(away_recent, away_col)
        values = pd.concat([home_totals.dropna(), away_totals.dropna()], ignore_index=True)
    else:
        side = _team_side_from_selection(fixture, odds.selection)
        if side is None:
            return 0.5
        if side:
            own_rows = history[history["home_team"] == fixture.home_team].sort_values("date").tail(20)
            opp_rows = history[history["away_team"] == fixture.away_team].sort_values("date").tail(20)
            values = pd.concat([_clean_stat(own_rows, home_col), _clean_stat(opp_rows, home_col)], ignore_index=True)
        else:
            own_rows = history[history["away_team"] == fixture.away_team].sort_values("date").tail(20)
            opp_rows = history[history["home_team"] == fixture.home_team].sort_values("date").tail(20)
            values = pd.concat([_clean_stat(own_rows, away_col), _clean_stat(opp_rows, away_col)], ignore_index=True)

    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return 0.5
    outcomes = values > line if is_over else values < line
    return beta_posterior_mean(int(outcomes.sum()), int(len(outcomes)))


def _market_evidence(
    goal_probs: dict[str, float],
    history: pd.DataFrame,
    fixture: Fixture,
    odds: OddsSnapshot,
) -> tuple[float, int, float, str] | None:
    goal_probability = _goal_market_probability(goal_probs, odds)
    if goal_probability is not None:
        sample_n = max(1, min(_team_sample_count(history, fixture.home_team), _team_sample_count(history, fixture.away_team)))
        return (
            float(goal_probability),
            sample_n,
            float(_pattern_strength(history, fixture, odds.market_key, odds.line)),
            "goals_poisson",
        )

    count_probability = _count_market_probability(history, fixture, odds)
    if count_probability is not None:
        probability, sample_n = count_probability
        return (
            float(probability),
            sample_n,
            float(_count_pattern_strength(history, fixture, odds)),
            "count_poisson_venue_opponent",
        )
    return None


def _combo_grade(combo: Combination) -> str:
    grades = [quality_grade(leg) for leg in combo.legs]
    if all(g == "A_STRONG_EDGE" for g in grades):
        return "A_STRONG_EDGE"
    if all(g in {"A_STRONG_EDGE", "B_POSITIVE_EDGE"} for g in grades):
        return "B_POSITIVE_EDGE"
    return "C_BEST_AVAILABLE"


def _store_recommendation(session, combo: Combination, target_label: str) -> None:
    recommendation = Recommendation(
        target_label=target_label,
        total_odds=combo.total_odds,
        joint_probability=combo.joint_probability,
        expected_value=combo.expected_value,
        quality_grade=_combo_grade(combo),
    )
    session.add(recommendation)
    session.flush()
    for leg in combo.legs:
        session.add(
            RecommendationLeg(
                recommendation_id=recommendation.id,
                fixture_id=leg.fixture_id,
                market_key=leg.market_key,
                selection=leg.selection,
                decimal_odds=leg.decimal_odds,
                model_probability=leg.model_probability,
            )
        )


def run_daily_pipeline(
    engine: Engine,
    report_date: date,
    now: datetime,
    preview_dir: Path,
    max_price_age: timedelta = timedelta(days=3),
    window: tuple[datetime, datetime] | None = None,
    candidate_limit: int | None = None,
) -> DailyRunResult:
    now = _utc_aware(now)
    Session = session_factory(engine)
    with Session.begin() as session:
        cutoff_date = min(report_date, window[0].date()) if window else report_date
        from .team_insights import load_history, team_key, COMPETITIONS, LEAGUE_CODES, competition_history
        history = load_history(engine, datetime.combine(cutoff_date, datetime.min.time(), tzinfo=timezone.utc))
        if history.empty:
            raise ValueError("no completed historical matches are available")
        goal_models = {}
        league_ids = {r.provider_key:r.canonical_key for r in session.scalars(select(ProviderMapping).where(
            ProviderMapping.source == 'api-football', ProviderMapping.entity_type == 'fixture_league'))}

        model_versions: dict[str, ModelVersion] = {}

        def model_version_for(model_name: str) -> ModelVersion:
            cached = model_versions.get(model_name)
            if cached is not None:
                return cached
            version = session.scalar(
                select(ModelVersion).where(
                    ModelVersion.model_name == model_name,
                    ModelVersion.version == "0.1.0",
                )
            )
            if version is None:
                version = ModelVersion(model_name=model_name, version="0.1.0")
                session.add(version)
                session.flush()
            model_versions[model_name] = version
            return version

        query = select(Fixture).where(Fixture.status == "SCHEDULED")
        if window:
            query = query.where(Fixture.kickoff >= window[0].replace(tzinfo=None),
                                Fixture.kickoff < window[1].replace(tzinfo=None))
        else:
            query = query.where(Fixture.match_date == report_date)
        target_fixtures = session.scalars(query).all()

        candidates: list[Candidate] = []
        scanned_markets = 0
        for fixture in target_fixtures:
            if fixture.kickoff is not None and _utc_aware(fixture.kickoff) <= now:
                continue
            snapshots = session.scalars(
                select(OddsSnapshot)
                .where(OddsSnapshot.fixture_id == fixture.id)
                .order_by(OddsSnapshot.received_timestamp.desc())
            ).all()
            scanned_markets += len(snapshots)
            league_id = league_ids.get(fixture.provider_id) if fixture.source == 'api-football' else None
            competition = LEAGUE_CODES.get(league_id, 'api:'+league_id) if league_id else COMPETITIONS.get(fixture.competition, fixture.competition)
            scoped_history = competition_history(history,fixture.competition,fixture.home_team,fixture.away_team,league_id)
            if not scoped_history.empty:competition=str(scoped_history.competition.iloc[0])
            model_fixture = SimpleNamespace(home_team=team_key(fixture.home_team), away_team=team_key(fixture.away_team))
            # League averages are not evidence for teams absent from training data.
            if (_team_sample_count(scoped_history, model_fixture.home_team) == 0
                    or _team_sample_count(scoped_history, model_fixture.away_team) == 0):
                continue
            if competition not in goal_models:
                goal_models[competition] = fit_poisson_goal_model(scoped_history, cutoff=pd.Timestamp(cutoff_date))
            goal_model = goal_models[competition]
            probs = goal_model.market_probabilities(model_fixture.home_team, model_fixture.away_team)
            from .learning import apply_learned_forecast
            learned = apply_learned_forecast(engine, scoped_history.assign(competition=competition),
                fixture.home_team, fixture.away_team, {'available':True,'probabilities':probs}, now)
            probs = learned['probabilities']

            # Keep the newest snapshot for each market/selection/line, preferring the
            # best price when multiple free sources share the same timestamp window.
            latest: dict[tuple, OddsSnapshot] = {}
            for snapshot in snapshots:
                key = (snapshot.market_key, snapshot.selection, snapshot.line)
                existing = latest.get(key)
                if existing is None:
                    latest[key] = snapshot
                else:
                    if snapshot.received_timestamp > existing.received_timestamp:
                        latest[key] = snapshot
                    elif snapshot.received_timestamp == existing.received_timestamp and snapshot.decimal_odds > existing.decimal_odds:
                        latest[key] = snapshot

            for snapshot in latest.values():
                evidence = _market_evidence(probs, scoped_history, model_fixture, snapshot)
                if evidence is None:
                    continue
                p, min_n, pattern_strength, model_name = evidence
                min_n = max(1, int(min_n))
                uncertainty = max(0.03, min(0.15, 0.20 / sqrt(min_n)))
                completeness = min(1.0, min_n / 10.0)
                data_quality = 0.65 + 0.30 * completeness
                price_time = _utc_aware(snapshot.received_timestamp)
                candidate = Candidate(
                    fixture_id=fixture.id,
                    fixture_key=f"{fixture.home_team} v {fixture.away_team}",
                    market_key=snapshot.market_key,
                    selection=snapshot.selection,
                    decimal_odds=float(snapshot.decimal_odds),
                    model_probability=float(p),
                    uncertainty=float(uncertainty),
                    data_quality=float(data_quality),
                    pattern_strength=float(pattern_strength),
                    price_timestamp=price_time,
                    fixture_resolved=True,
                    line=snapshot.line,
                    bookmaker=snapshot.bookmaker,
                    model_version=learned.get('model_version', 'poisson-baseline-v1') if model_name == 'goals_poisson' else model_name + '-v1',
                )
                validation = validate_candidate(candidate, now, max_price_age)
                if not validation.valid:
                    continue
                candidates.append(candidate)
                model_version = model_version_for(model_name)
                session.add(
                    Prediction(
                        fixture_id=fixture.id,
                        model_version_id=model_version.id,
                        market_key=snapshot.market_key,
                        selection=snapshot.selection,
                        probability=float(p),
                        lower_bound=max(0.0, float(p) - uncertainty),
                        upper_bound=min(1.0, float(p) + uncertainty),
                        feature_cutoff=now.replace(tzinfo=None),
                    )
                )

        search_candidates = candidates
        if candidate_limit is not None:
            search_candidates = sorted(candidates, key=lambda c: c.ev, reverse=True)[:candidate_limit]
        best_2x_list = optimize_combinations(search_candidates, 1.80, 2.30, max_legs=4)
        best_3x_list = optimize_combinations(search_candidates, 2.60, 3.50, max_legs=4)
        best_2x = best_2x_list[0] if best_2x_list else None
        best_3x = best_3x_list[0] if best_3x_list else None

        if best_2x is not None:
            _store_recommendation(session, best_2x, "2X")
        if best_3x is not None:
            _store_recommendation(session, best_3x, "3X")

        report = DailyReport(
            report_date=report_date.isoformat(),
            generated_at=now,
            best_2x=best_2x,
            best_3x=best_3x,
            scanned_matches=len(target_fixtures),
            scanned_markets=scanned_markets,
            valid_candidates=len(candidates),
        )

    rendered = render_daily_report(report)
    text_path, html_path = save_preview(rendered, preview_dir)
    return DailyRunResult(report=report, text_path=text_path, html_path=html_path,
                          combinations_2x=best_2x_list, combinations_3x=best_3x_list,
                          search_candidates=len(search_candidates))
