# Free Live Source & Market Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add an optional $0 API-FOOTBALL live-data adapter with quota awareness and expand the daily engine beyond 1X2/goals to team count markets whenever trustworthy odds and historical statistics exist.

**Architecture:** API-FOOTBALL is an optional provider: the application runs without a key, and with a free key it can ingest fixtures and pre-match odds into the same canonical tables used by Football-Data.co.uk. Count-market probabilities are produced by the existing transparent count models from historical team/opponent statistics; unsupported or missing data fail closed rather than creating picks.

**Tech Stack:** Python 3.12+, httpx, SQLAlchemy 2.x, pandas, NumPy/SciPy/statsmodels, Typer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-betting-analytics-design.md`

## Global Constraints

- Required recurring cost is $0.
- API-FOOTBALL free tier is optional and must never be required for offline/backtest operation.
- Never invent odds, team statistics, lineups, injuries, or player data.
- Respect the provider quota; expose remaining request counts returned by response headers.
- Only canonical markets understood by the model are ingested for recommendations; unknown markets fail closed.
- Official 2x/3x recommendations remain cross-match combinations in V1.
- No automated bet placement.

---

### Task 1: API-FOOTBALL free client and quota metadata

**Files:**
- Create: `src/betmodel/providers/api_football.py`
- Create: `tests/test_api_football.py`
- Modify: `src/betmodel/config.py`

**Interfaces:**
- Produces: `ApiFootballClient(api_key, http=None, base_url=...)`
- Produces: `ApiQuota(limit, remaining, minute_limit, minute_remaining)`
- Produces: `fetch_fixtures(date: str) -> tuple[list[FixtureRecord], ApiQuota]`
- Produces: `fetch_odds(fixture_id: str) -> tuple[list[ApiFootballOdds], ApiQuota]`

- [x] Write failing tests for missing key, fixture parsing, quota headers, and odds parsing.
- [x] Run the tests and confirm they fail because the provider module does not exist.
- [x] Implement only the provider/client and settings property required by the tests.
- [x] Run the provider tests and full suite.
- [x] Commit.

### Task 2: Canonical API-FOOTBALL market mapping and ingestion

**Files:**
- Modify: `src/betmodel/providers/api_football.py`
- Modify: `src/betmodel/normalize.py`
- Modify: `src/betmodel/ingest.py`
- Create: `tests/test_api_football_ingest.py`

**Interfaces:**
- Produces: canonical odds records for match result, total goals, BTTS, corners, cards, team shots and team SOT only when provider market names/values can be mapped unambiguously.
- Produces: `ingest_api_football(engine, fixtures, odds_by_fixture) -> IngestSummary`.

- [x] Write failing tests for canonical mapping and idempotent fixture/odds ingestion.
- [x] Run and verify the intended failures.
- [x] Implement minimal mapping and ingestion; unknown markets are skipped.
- [x] Run focused and full tests.
- [x] Commit.

### Task 3: Quota-aware sync command

**Files:**
- Modify: `src/betmodel/cli.py`
- Create: `tests/test_cli_api_football.py`

**Interfaces:**
- Produces: CLI `sync-api-football --date YYYY-MM-DD` that fetches the date slate once, fetches odds only for returned fixtures while a configurable reserve remains, ingests them, and prints quota remaining.

- [x] Write a failing CLI test using a fake client; no network calls in tests.
- [x] Run and verify failure.
- [x] Implement the command and quota reserve guard.
- [x] Run focused and full tests.
- [x] Commit.

### Task 4: Count-market probability support in daily recommendations

**Files:**
- Modify: `src/betmodel/daily.py`
- Modify: `src/betmodel/pattern_insights.py` only if reusable helpers are needed.
- Create: `tests/test_daily_count_markets.py`

**Interfaces:**
- Daily model supports `TOTAL_CORNERS_OVER/UNDER`, `TEAM_CORNERS_OVER/UNDER`, `TOTAL_CARDS_OVER/UNDER`, `TEAM_SHOTS_OVER/UNDER`, `TEAM_SOT_OVER/UNDER` when history contains enough observations and a matching odds snapshot exists.
- Missing statistics or unsupported lines return no candidate, never a guessed probability.

- [x] Write failing synthetic end-to-end tests with corner/SOT odds and known historical rates.
- [x] Run and verify failure.
- [x] Implement minimal transparent count probability generation and evidence-aware pattern strength.
- [x] Run focused and full tests.
- [x] Commit.

### Task 5: Documentation and smoke verification

**Files:**
- Modify: `docs/superpowers/specs/2026-09-17-zero-cost-betting-analytics-design.md`
- Create: `README.md`

**Interfaces:**
- README documents zero-cost setup, offline mode, optional free API key, commands, and limitations.

- [x] Update spec to document API-FOOTBALL free adapter and 100-request/day design constraint.
- [x] Write README with exact local commands and environment variables.
- [x] Run `PYTHONPATH=src python -m pytest -q`.
- [x] Run CLI help smoke test.
- [x] Commit.

### Task 6: Free SMTP send path for automation

**Files:**
- Modify: `src/betmodel/cli.py`
- Modify: `tests/test_cli_daily.py`

**Interfaces:**
- `betmodel daily ... --send` sends the same deterministic report through SMTP using environment variables `SMTP_HOST`, `SMTP_PORT`, `SMTP_SENDER`, `SMTP_RECIPIENT`, optional `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_TLS`.
- Without `--send`, behavior remains preview-only and requires no email credentials.

- [x] Write a failing CLI test that verifies `--send` calls SMTP with environment configuration and that missing required SMTP variables fail closed.
- [x] Run and verify failure.
- [x] Implement the minimal send path using the existing `send_smtp` helper.
- [x] Run focused and full tests.
- [x] Commit.
