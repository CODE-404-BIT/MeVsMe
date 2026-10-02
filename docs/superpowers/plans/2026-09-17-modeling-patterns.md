# Zero-Cost Modelling & Pattern Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build leakage-safe team-level football probability models and a perfect/near-perfect pattern scanner from the normalized free historical data.

**Architecture:** Feature builders operate only on rows preceding the target fixture date. Statistical models remain simple and inspectable, with calibration and walk-forward evaluation. Pattern probabilities use Bayesian shrinkage rather than raw 100% hit rates.

**Tech Stack:** Python, pandas, NumPy, SciPy, statsmodels, scikit-learn, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-modeling.md`

## Global Constraints
- No future match/result/closing-price leakage.
- Raw historical 100% hit rate can never be emitted as 100% forecast probability.
- Every prediction carries model version and feature cutoff timestamp.
- Player prop models remain disabled until trustworthy free player-level inputs exist.

---

## File Structure
- `src/betmodel/features.py` — leakage-safe rolling features.
- `src/betmodel/patterns.py` — hit-rate windows and Bayesian shrinkage.
- `src/betmodel/models_goals.py` — Poisson/Dixon-Coles baseline utilities.
- `src/betmodel/models_counts.py` — corners/cards/shots count models.
- `src/betmodel/calibration.py` — probability calibration helpers.
- `src/betmodel/backtest.py` — walk-forward evaluation.
- `tests/test_features.py`, `tests/test_patterns.py`, `tests/test_models.py`, `tests/test_backtest.py`.

### Task 1: Leakage-safe rolling feature builder

**Interfaces:**
- `build_team_rolling_features(matches: DataFrame, windows=(5,10,20)) -> DataFrame`
- Each target row uses only matches with `date < target_date`.

- [ ] Write a failing test where a future 10-goal match must not affect an earlier row's rolling average.
- [ ] Run and confirm failure.
- [ ] Implement sort/group/shift/rolling logic with explicit `shift(1)`.
- [ ] Run tests and confirm pass.
- [ ] Commit.

### Task 2: Pattern scanner with Beta shrinkage

**Interfaces:**
- `beta_posterior_mean(hits: int, trials: int, alpha=1.0, beta=1.0) -> float`
- `scan_patterns(frame, market_fn, windows=(5,10,20)) -> list[PatternResult]`

- [ ] Write tests asserting `5/5` and `20/20` both produce probabilities below 1.0 and `20/20 > 5/5` under the same prior.
- [ ] Run and confirm failure.
- [ ] Implement Beta posterior mean and Wilson/Beta interval.
- [ ] Run tests and confirm pass.
- [ ] Commit.

### Task 3: Goal model baseline

**Interfaces:**
- `fit_poisson_goal_model(history: DataFrame, cutoff: date) -> GoalModel`
- `GoalModel.score_matrix(home_team, away_team, max_goals=8) -> ndarray`
- `GoalModel.market_probabilities(...) -> dict[str, float]`

- [ ] Create synthetic league data with known attack/defence tendencies and failing probability-sum tests.
- [ ] Implement league/home advantage plus attack/defence Poisson baseline.
- [ ] Verify score matrix sums to approximately 1 and market probabilities are bounded.
- [ ] Add regression tests for Over 2.5, BTTS, home/draw/away.
- [ ] Commit.

### Task 4: Count models for corners/cards/shots

**Interfaces:**
- `fit_count_model(history, stat_column, cutoff, distribution="poisson") -> CountModel`
- `CountModel.prob_over(line: float, context: dict) -> float`

- [ ] Write failing synthetic tests for Poisson tail probability and missing-stat rejection.
- [ ] Implement Poisson baseline and optional negative-binomial dispersion estimate.
- [ ] Run tests.
- [ ] Commit.

### Task 5: Probability calibration

**Interfaces:**
- `fit_isotonic_calibrator(probabilities, outcomes) -> Calibrator`
- `calibration_report(probabilities, outcomes) -> dict`

- [ ] Write tests showing calibrated values remain in [0,1] and Brier score utility matches hand calculation.
- [ ] Implement isotonic calibration with minimum-sample guard; identity calibrator below threshold.
- [ ] Run tests.
- [ ] Commit.

### Task 6: Walk-forward backtester

**Interfaces:**
- `walk_forward_backtest(matches, train_min, predict_fn) -> BacktestReport`
- Metrics: Brier, log loss, hit rate, ROI when odds are available, per-market counts.

- [ ] Write a failing test that records the maximum training date for each prediction and asserts it is earlier than fixture date.
- [ ] Implement chronological folds with no random split.
- [ ] Add metric calculations and per-market breakdown.
- [ ] Run full tests.
- [ ] Commit.
