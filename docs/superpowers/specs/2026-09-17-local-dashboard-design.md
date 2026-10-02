# Local match and combination dashboard

## Objective

Replace repeated terminal commands with a local browser dashboard. A Windows launcher starts the server and opens the dashboard. The existing CLI continues to work.

## Approach

Use a small Python web server, the existing SQLite database and modeling services, and HTML/CSS/JavaScript assets. Keep installation within the existing virtual environment. Bind to loopback only. A native desktop app would add packaging complexity; a hosted app would add deployment and credential management beyond the requested local workflow.

## Interface

A responsive sports dashboard with a dark navy background, clear white typography, teal primary actions, spacious cards and readable tables. Navigation: Matches of the Day, 2× Combinations, 3× Combinations, Settings. Show date, last update, API quota and loading status. Include search, competition filters and status filters.

The Matches of the Day button loads saved fixtures immediately and requests a refresh for the selected day. Display all returned fixtures, including finished and postponed matches, with explicit status. Kickoff times are displayed in the browser's local timezone. Query dates must be translated into the provider's UTC dates when needed to cover the selected local day. Match cards show competition, teams, kickoff, available markets and history coverage. Fixture availability is limited by the provider's coverage, and the UI must say so.

Separate 2× and 3× buttons analyze saved data and display multiple distinct combinations in the existing odds ranges (1.80–2.30 and 2.60–3.50). Use pagination, rather than showing only the highest-ranked combination. Show result counts, ordering and any explicit search limits; do not claim exhaustive enumeration if a bounded search is used. Avoid duplicate combinations differing only by stale prices or bookmaker copies. Each card names the market (for example Both Teams to Score — Yes), legs, total odds, model probability, EV, uncertainty and history coverage.

Use “combinations” rather than “stakes”: the requested 2×/3× figures describe combined decimal odds, not money to wager. No stake sizing or bet placement is included.

## Data behavior

Keep matches visible even when they cannot be modeled. Require historical evidence for both teams before emitting predictions; do not reuse unrelated league averages for unknown teams. Explain empty results with concrete missing-data reasons. Separate available combinations from those meeting the displayed +5% EV target, and label negative EV clearly. Do not promise profitable selections.

Reuse rate-limit handling, fetch odds only for upcoming scheduled fixtures, and show partial completion. Prevent concurrent duplicate syncs from repeated button clicks. Preserve downloaded data. Prioritize missing odds so repeated refreshes do not consume the entire allowance on the same initial matches. Display provider errors in the page without raw tracebacks or secrets.

Settings allows entry of the API key without echoing it into page responses or logs. Default to the existing environment variable; a session-only key may be supplied in the UI. Do not persist credentials in browser storage or plaintext project files.

## Implementation boundaries

Add web routes, dashboard assets and a Windows launcher. Extract reusable analysis results from the daily pipeline so both the CLI report and dashboard use the same calculations. Keep network sync and analysis off the request thread with one background task at a time and status polling. Reuse the existing database schema where possible. The launcher must detect an already-running server and open it instead of starting duplicates.

## Validation

Test match listing and local-day boundaries, API key redaction, background job lifecycle, rate-limit and partial-result handling, preservation of unknown-team exclusion, multiple combination results and pagination. Run existing modeling tests after refactoring. Verify the browser layout, button states, errors and empty results, then start the app locally and provide the URL and launcher path.

## Known constraint

The database currently has Premier League historical statistics. The dashboard cannot create supported predictions for other teams until matching history is loaded. This is displayed explicitly and is not bypassed to populate cards.
