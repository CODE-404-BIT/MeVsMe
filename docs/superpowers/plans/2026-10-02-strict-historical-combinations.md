# Strict historical combinations implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task if native execution is selected; use superpowers:subagent-driven-development if the user selects delegation. Steps use checkbox syntax for tracking.

**Goal:** Make the football 2x/3x views show only fresh priced combinations supported by exact 100% historical records, with no fallback slips.

**Architecture:** Share explicit evidence eligibility between insights and the combination pipeline. Preserve existing odds matching and historical performance records. Validate cached results against current fixture/price state before serving them.

**Tech Stack:** Python 3.12+, SQLAlchemy, pytest, existing Flask/local HTTP transports and vanilla JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-02-multi-sport-recommendations-design.md`

## Global constraints

- 100% means hits == trials with at least five settled observations in a predefined 5/10/20 window; it is not a future probability.
- Prices must be finite and >1, no more than 24 hours old, not future dated, and match the exact participant/line/market/venue.
- Distinct upcoming events, one bookmaker, 1.80-2.30 for 2x and 2.60-3.50 for 3x, at most four legs.
- No model/EV gate on historical combinations; no unpriced fallback cards or fallback API output.
- Preserve private login, SQLite/PostgreSQL support, existing IDs, frozen historical snapshots and zero recurring cost.
- Do not publish this stage as completion of the multi-sport request.

## Review focus

- A previously valid cached event starts or is cancelled: exclude it on the next response (task 2).
- Latest quote is invalid/stale but an older quote is valid: do not silently revive the old quote (task 1).
- A perfect record refers to a different venue or a future observation: exclude it (task 1).
- Browser requests race across dates or tabs: do not render results for the wrong selection (task 3).
- Existing frozen predictions have no new evidence fields: keep their history readable and immutable (task 2).

## Task 1: shared evidence eligibility

**Files:** modify `src/betmodel/historical_suggestions.py`, `src/betmodel/team_insights.py`; test `tests/test_historical_suggestions.py`.

**Interfaces:** add `qualifying_patterns(match: dict, now: datetime) -> list[dict]`; consume existing `pattern_market`, `suggestions` and `historical_patterns`. Return original display fields plus normalized market identity, age and stale flag. `suggestions` remains an adapter returning match dictionaries with qualifying patterns.

- [ ] Add failing tests `test_perfect_record_rejects_one_failure_or_short_sample`, `test_future_observation_cannot_support_pick`, `test_perfect_record_preserves_venue_and_exact_line`, `test_latest_invalid_quote_does_not_revive_older_quote`. Assert 4/5, 4/4, future records and away evidence for a home-only market are excluded; 5/5 is accepted without a forecast.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests/test_historical_suggestions.py -q`; confirm the new assertions fail for the intended reason.
- [ ] Implement structured eligibility, retaining existing label parsing only at the legacy boundary. Use the same qualifying result for insights and priced selection. Display all 5/10/20 windows for that market, without treating nested windows as independent trials.
- [ ] Run the same tests and existing `tests/test_team_insights.py` and `tests/test_accuracy_policy.py`; require all to pass. Record the passing output before commit.

## Task 2: strict API output and current eligibility

**Files:** modify `src/betmodel/accuracy_policy.py`, `src/betmodel/dashboard.py`, `src/betmodel/historical_suggestions.py`; extend `tests/test_historical_suggestions.py`, `tests/test_dashboard.py`, `tests/test_performance.py`.

**Interfaces:** `analyze_evidence(engine, window, now=None)` retains its tuple of combinations/report but removes `historical_slips` output. Add `current_combinations(engine, items: list[dict], now: datetime) -> list[dict]` to validate current fixture status/start and latest quote identity/value/timestamp. `Dashboard.combinations` calls it before counting and paginating. Changed quotes exclude cached cards until reanalysis instead of changing frozen snapshots.

- [ ] Write failing tests `test_no_unpriced_fallback_when_prices_missing`, `test_cached_combination_disappears_at_kickoff`, `test_cancelled_event_removed_without_reanalysis`, `test_replaced_or_expired_quote_invalidates_cache`, `test_revalidation_preserves_frozen_history`. Assert empty item lists/no fallback key, accurate totals, and unchanged persisted JSON.
- [ ] Run affected tests and confirm the new failures.
- [ ] Remove active `build_historical_slips` usage. Keep its old helper only if another supported caller needs it; tests must no longer require its exposure through payout API responses. Add response-time validation with batched fixture/quote reads. Preserve `joint_probability=None` and `ev=None` on historical cards.
- [ ] Run affected tests plus `tests/test_odds_only.py`, `tests/test_cloud_http.py`; require passing results before commit.

## Task 3: payout UI and precise empty states

**Files:** modify `src/betmodel/static/accuracy-policy.js`; extend `tests/browser_historical_patterns.py`; document in `README.md`.

**Interfaces:** render existing combination fields; use `analysis.reason` for the empty explanation. No new transport endpoint.

- [ ] Add browser cases for qualifying evidence with missing prices (zero combo cards/no unpriced section), two exact 1.45 prices (one 2.1025 payout), one 4/5 leg (no card), and rapid tab/date changes (only latest response renders).
- [ ] Execute the browser script against an isolated test database and confirm failures before editing UI.
- [ ] Remove unpriced counts, slip sections and fallback wording. Show qualifying records, date range, freshness and bookmaker for every priced leg. Retain a concise empty state and refresh action. Update README to describe this behavior.
- [ ] Run `tests/browser_historical_patterns.py` and the affected Python tests. Inspect desktop/mobile output and JavaScript errors. No production DB is used for tests.

## Integration checkpoint

- [ ] Compare changed files with the authenticated GitHub checkout when available; never overwrite remote changes using the stale local source archive.
- [ ] Commit a tested change with title `fix: require priced perfect evidence in payout views` once a Git checkout exists. Until then record an exact file list; no fictitious commit identifier.
- [ ] Continue to `2026-10-02-multi-sport-discovery-ranking.md`; do not call the overall task complete.
