# Local Dashboard Implementation Plan

> Execute inline using the executing-plans workflow; the user has approved implementation.

**Goal:** Open a local dashboard from a Windows launcher and run match sync and multiple-combination analysis with buttons.
**Architecture:** Python standard-library HTTP server, background job service, existing SQLite/model code, static HTML/CSS/JS. No additional runtime dependencies.
**Spec:** ../specs/2026-09-17-local-dashboard-design.md
**Constraints:** Loopback only; session-only credentials; all provider fixtures visible; local calendar days; unknown teams excluded; explicit bounded search; no real bets.

## 1. Analysis and sync services
- [x] Add regression tests for local-day boundaries and unknown-history matches; run them before implementation.
- [x] Extend `run_daily_pipeline` with optional UTC window, candidate search cap and full combination lists on `DailyRunResult`. Preserve CLI compatibility.
- [x] Add optional fixture-priority callback to `sync_api_football`; preserve downloaded fixtures and avoid repeatedly prioritizing fresh odds.
- [x] Run daily and sync tests.

## 2. Dashboard service and HTTP API
- [x] Create `src/betmodel/dashboard.py`: local date/offset parsing, fixture/history coverage listing, in-memory job state, single background worker, paginated analysis results, masked configuration, bounded API sync across UTC dates.
- [x] Create `src/betmodel/web.py`: static assets and JSON endpoints; validate Host, Origin and a page token for writes; no arbitrary file paths or raw errors. Provide `python -m betmodel.web` entry point.
- [x] Tests in `tests/test_dashboard.py`: date boundaries, match listing, pagination, concurrency, job errors, credential redaction and HTTP request protections.

## 3. Interface and launcher
- [x] Add `src/betmodel/static/index.html`, `app.css`, `app.js`: responsive navy/teal interface, date/search/competition/status filters, match cards, 2×/3× tabs, EV filters, pagination, job polling, settings dialog with a password field.
- [x] Create `Launch Dashboard.vbs` and `launch-dashboard.ps1`: hidden Python process, per-project port check, reuse existing server, readiness check and browser open. Errors must be visible and actionable.
- [x] Package static assets and existing report templates; document launch and data limitations in README.

## 4. Verification
- [x] Run the full pytest suite and resolve introduced failures.
- [x] Start the dashboard and verify match API against actual saved data, unknown-history exclusions and analysis job completion.
- [x] Use a browser automation tool if locally available; otherwise install Playwright for development verification, inspect desktop/mobile screenshots and test clicks.
- [x] Review implementation for secret leaks, date mismatches, unsafe HTML insertion, concurrent refreshes and unbounded optimization.
- [x] Open the working dashboard and report its URL, launcher and limitations.
