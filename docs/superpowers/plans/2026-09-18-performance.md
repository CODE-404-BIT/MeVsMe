# Performance and learning implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Record and evaluate generated combinations and introduce measured model updates.
**Architecture:** Separate tracking/settlement and learning modules backed by SQLite; dashboard orchestrates jobs and exposes summaries. Browser shows persistent cohort statistics and diagnostics.
**Tech Stack:** Python, SQLAlchemy, scipy/pandas, standard-library HTTP, browser JavaScript.
**Spec:** docs/superpowers/specs/2026-09-18-performance-design.md

## Global constraints
- Freeze pre-kickoff records; do not backfill prospective accuracy.
- Preserve odds-only versus model cohorts; no guaranteed results.
- Keep provider quotas, local-only security and session-only credentials.
- No git repository; edit this existing user-authorized workspace.

## Task 1: Tracking and settlement
- [x] Add tests for deduplication, immutable prices, post-kickoff exclusion, full/half wins and losses, refunds, pending and missing markets.
- [x] Implement `performance.py`: `record_combinations(engine,target,mode,items,now=None)`, `settle_saved(engine)`, `performance_summary(engine)`, `pending_fixture_ids(engine)`.
- [x] SQLite records own JSON snapshots; leg keys fixture_id, market_key, selection, line, odds, bookmaker; combo joint_probability optional, model_version optional.
- [x] Verify with `python -m pytest tests/test_performance.py -q`.

## Task 2: Learning
- [x] Write chronological selection/promotion tests, cold start and persistence tests.
- [x] Implement `learning.py`: `update_models(engine,now=None)`, `learning_summary(engine)`, `apply_learned_forecast(engine,pool,home,away,forecast,cutoff)`.
- [x] Train shrinkage candidates on earlier development, evaluate champion/challenger later; freeze version/cutoff; never modify saved forecasts. Integrate in team_insights only.
- [x] Verify `python -m pytest tests/test_learning.py -q`.

## Task 3: Dashboard and results fetch
- [x] Integration tests for status stats, job routing and settlement of saved IDs independent of selected day.
- [x] Wire record hooks for both combination modes; add result refresh and model update jobs, cap provider result requests and preserve partial results.
- [x] Add top-right summary with cohort selector, counts, win rate, ROI and empty-sample language. Add per-match recommendation diagnostics and clear odds-only badge explanation.
- [x] Verify focused tests then full suite and real-browser desktop/mobile rendering.

## Task 4: Review and delivery
- [x] Review settlement, leakage, promotion, identities, quota and request safety; fix findings.
- [x] Update README, restart local dashboard, verify HTTP and screenshots.

## Decisions
- Win rate means strictly full wins / (full wins + full losses); partial outcomes and refunds shown separately, excluded from binary probability scores.
- Counts are unique generated combinations within the bounded search, not bets placed; first snapshot wins across price/model revisions.

## Verification and review
126 tests pass, including HTTP routes. Real Chrome desktop/mobile checks pass with no JavaScript errors. Review fixed cancellation provenance, frozen leg metadata, missing champion-team fallback and canonical daily history. Five real league evaluations retained baseline; zero accepted upgrades. Session API key is absent after restart, so provider settlement was tested with controlled responses, not a live credential. No git repository is present.
