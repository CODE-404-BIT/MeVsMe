# Multi-sport discovery and ranking implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if the user selects delegation. Steps use checkbox syntax for tracking.

**Goal:** Automatically discover football, basketball, tennis and ice-hockey events, rank up to ten supported picks and expose genuine coverage limits.

**Architecture:** Add sport-aware storage/providers alongside the existing football tables. Feed normalized event, evidence and model results into one recommendation service. Reuse existing authentication, durable job locks and checkpoint storage.

**Tech Stack:** Python 3.12+, SQLAlchemy, httpx, existing numerical libraries, pytest and vanilla JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-02-multi-sport-recommendations-design.md`

## Global constraints

- Zero paid services; no silent upgrades. Each sport requires verified accessible results and events, not merely a tab.
- One market per event, maximum ten ranked events across the four sports. Do not fill missing places with invented or ineligible picks.
- Model estimates, historical hit rates and bookmaker-implied probabilities remain different fields and labels.
- Historical combinations retain all rules from `2026-10-02-strict-historical-combinations.md`.
- Retain existing football tables/IDs and authenticated routes; new schemas are additive and work in SQLite/PostgreSQL.
- At least 100 chronological held-out predictions and improvement over baseline Brier score are required for model promotion.

## Review focus

- Cross-sport/provider event ID collisions and similar participant names must not merge unrelated events (task 2).
- Overtime, regulation, tennis retirement and walkover distinctions must survive normalization (tasks 1-2).
- Provider failure, missing credentials and quota exhaustion must leave other sports usable without fabricated coverage (tasks 1, 3).
- Historical rows or results available after a prediction cutoff must not enter training or evaluation (task 4).
- Restarts and simultaneous browsers must not duplicate requests or reset budgets; no secret may enter error messages (tasks 3, 5).

## Task 1: verify actual provider contracts

**Files:** create `docs/multi-sport-sources.md` and sanitized samples under `tests/fixtures/multisport/`.

**Interfaces:** document each verified feed's endpoint, request parameters, event/participant identifiers, UTC dates, status, settlement scope, pagination, quotas and history availability. Samples must be actual responses without credentials or account identifiers.

- [ ] Validate API-Sports basketball/hockey access using separately configured credentials; validate The Odds API active-sport/event/odds schema and Australian bookmaker coverage. Never assume the football entitlement works for other sports.
- [ ] Find and validate a permitted free tennis singles results source. Verify current results, historical coverage and stable player identities; document retirement/walkover handling. If still unavailable, record the concrete failed access checks and leave the tennis delivery incomplete. Do not replace this task with fabricated fixtures or claim four-sport completion.
- [ ] Capture one scheduled and one completed event per sport plus negative examples (cancelled/incomplete/retirement). Capture a real quote with settlement semantics. Tests may use synthetic edge cases in addition to these samples.
- [ ] Write provider contract tests in `tests/test_multisport_providers.py`; unknown status/scope must be rejected and 401/403/429 messages must be sanitized. The tennis adapter's exact schema is fixed only after a real accessible source is verified, not guessed beforehand.

## Task 2: normalized storage and idempotent ingestion

**Files:** create `src/betmodel/multisport_domain.py`, `multisport_store.py`, `providers/api_sports.py`, `providers/odds_api.py`, `providers/tennis_results.py`; modify `src/betmodel/db.py`; create `tests/test_multisport_store.py` and extend migration tests.

**Interfaces:** frozen dataclasses `SportEvent`, `SportResult`, `SportQuote` carry sport, provider, provider IDs, competition, participants, UTC timestamp, status/settlement scope and provenance. `SportQuote` also carries market, line, selection, bookmaker, decimal price and source timestamp. Expose `upsert_events(engine, events)`, `upsert_results(engine, results)`, `upsert_quotes(engine, quotes)` returning inserted/updated counts. Adapters accept injected httpx clients for offline tests. Football is bridged through a read adapter instead of copying its records.

- [ ] Add failing tests for two sports both using ID 1 (two events), replayed provider pages (no duplicates), ambiguous aliases (unresolved/excluded), incomplete scores (no settled result), regulation vs overtime (different markets), singles vs doubles (different participants/events).
- [ ] Define additive tables with unique `(sport, provider, provider_id)` keys and market identities including settlement scope. Validate numbers/dates before writes. Do not encode basketball scores or tennis sets in football goal columns. Register tables in `application_tables()` for backup/migration coverage.
- [ ] Implement adapters against task 1 samples; do not infer undocumented tennis column meanings. Preserve original result provenance and quote timestamps.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests/test_multisport_providers.py tests/test_multisport_store.py tests/test_cloud_migration.py -q`; repeat real PostgreSQL additive-schema tests. Existing football row counts and frozen JSON must match before/after.

## Task 3: bounded automatic refresh

**Files:** create `src/betmodel/multisport_refresh.py`; modify `dashboard.py`, `state_store.py`; create `tests/test_multisport_refresh.py`.

**Interfaces:** `refresh_sports(engine, window, providers, now, progress) -> dict` returns per-sport discovered/history-covered/priced counts, failures, quota state and timestamps. Persist cursors/budgets by provider and credential fingerprint. Add `Dashboard.start(kind='discover', ...)` using the existing exclusive job guard.

- [ ] Tests: two browser refreshes cause one provider run; restart retains consumed quota/cursor; an HTTP 429 pauses only that provider; local-day UTC boundaries fetch all relevant dates; keys never appear in progress/error JSON.
- [ ] Refresh event feeds on a 30-minute cache, odds at most once per 30 minutes, completed histories at most once per 6 hours. Data expiration never makes expired odds eligible. Persist source status separately from successful rows so a failed refresh cannot erase last known records.
- [ ] For The Odds API, retain 50 of 500 monthly credits as reserve; enforce a 14-credit daily cap and charge endpoint cost before calls, reconciling provider headers after responses. Unknown cost is not a free call. Round-robin active supported competitions across sports with persisted cursor, prioritizing events in the selected date window. Show incomplete coverage explicitly. API-Sports retains a reserve of 20 daily requests per enabled sport account and respects returned headers.
- [ ] Run refresh tests with fake clocks and restart/new-engine cases; then perform one bounded live smoke check per configured provider and record real counts without secrets.

## Task 4: chronological models and ranking

**Files:** create `src/betmodel/multisport_models.py`, `multisport_recommendations.py`; create `tests/test_multisport_models.py`, `tests/test_multisport_recommendations.py`.

**Interfaces:** `evaluate_winner_model(results, sport, cutoff) -> dict` returns model/version, chronological predictions, Brier/baseline and calibration report. `rank_picks(events, forecasts, evidence, quotes, now, limit=10) -> list[dict]` returns unique eligible event cards. `build_sport_combinations(events, evidence, quotes, now) -> dict` returns strict historical payout cards independent of model promotion.

- [ ] Add tests for perfect historical rate != 100% forecast, validation/train chronological separation, tennis surface separation, fewer than 100 held-out events (not promoted), model worse than baseline (not promoted), eleven eligible events (ten unique cards), no history (no invented probability), distinct event keys across sports.
- [ ] Retain football Poisson estimates. For other sports use regularized logistic winner models with pre-event participant Elo difference and rolling last-10 form, computed from settled results only; tennis additionally uses surface-specific Elo/history. Basketball/hockey are separate models by settlement scope. Fix model hyperparameters before holdout evaluation; do not tune on held-out predictions.
- [ ] Use chronological expanding evaluation, requiring 200 earlier settled training events before an evaluation prediction. Benchmark against a prior-only sport/scope baseline (home win rate for team sports, 0.5 for tennis). Calibration check: five fixed probability bins, at least 20 holdout predictions per evaluated bin, absolute forecast/observed gap <=0.10, and >=80% of predictions covered by evaluated bins. Otherwise mark unvalidated and keep outside ranked betting picks.
- [ ] Require at least ten past observations per participant for a ranked pick. Rank by validated probability, then minimum participant sample count, history recency, stable event ID; keep one market per event. Display odds only when current/exact; missing odds do not become invented prices or EV.
- [ ] Evidence confidence uses `min(9.9, 7*min(min_participant_sample/20,1) + 3*max(0,1-oldest_latest_age_days/180))`, with method labelled on the card. This is a coverage/recency score, never a win probability. Exclude forecasts if either participant's latest history is older than 180 days.
- [ ] Evaluate strict records over predefined 5/10/20 windows and exact normalized offered winner/half-point-total markets only when result scope matches. No ad-hoc threshold search. Whole-number push-capable totals and ambiguous settlement markets are excluded. Feed these records through the same strict combination eligibility from plan 1; retain bounded search and disclose truncation.
- [ ] Run model/recommendation tests plus existing football model/history tests. Save actual chronological evaluation metrics per sport; a failing promotion criterion remains failing rather than lowering thresholds to force ten picks.

## Task 5: API, scorecards and persisted snapshots

**Files:** modify `api_routes.py`, `dashboard.py`, `static/index.html`, `static/accuracy-policy.js`, `static/insights.css`; create `static/multisport.js`, `tests/test_multisport_http.py`, `tests/browser_multisport_check.py`; extend cloud authorization tests.

**Interfaces:** `GET /api/recommendations?date=...&offset=...&end_offset=...&sport=all` is read-only and returns `{items, research_estimates, coverage, updated_at, stale}`. POST the existing jobs endpoint with `kind=discover` to refresh under CSRF protection. The browser requests at most one refresh when stale. Store immutable model recommendation snapshots with model version/cutoff, selected market and evidence; retain historical combinations in their separate cohort. New snapshot tables join `application_tables()`.

- [ ] Add failing HTTP tests for unauthenticated reads/writes, absent CSRF, invalid sport/date, duplicate refresh and sanitized error output; browser cases for empty sport, ten-card limit, active filters, 401 redirect and narrow mobile width.
- [ ] Make Recommended Picks use the new API rather than the old JavaScript override chain. Add All/Football/Basketball/Tennis/Ice hockey filter and adjacent scorecard. Show win estimate, historical rate, sample/date range, form, evidence confidence, validation, odds freshness and coverage independently. Display unvalidated research estimates separately from ranked picks.
- [ ] Persist snapshots, deduplicating identical event/market/model/cutoff output. Add scope-aware settlement, rejecting unknown retirement/overtime semantics, and retain pending state when results are incomplete. Test that a restart preserves the same frozen evidence and does not overwrite past predictions.
- [ ] Run HTTP/browser checks and full Python suite once changes settle. Confirm automatic discovery works without team input, partial coverage is visible and no unpriced fallback is present.

## Handoff

- [ ] Record tested source access, model promotion reports, required new environment-variable names, actual supported competitions and any unmet sport requirements.
- [ ] Commit verified stages when Git is connected. Continue with `2026-10-02-live-multi-sport-release.md`; local tests alone are not live completion.
