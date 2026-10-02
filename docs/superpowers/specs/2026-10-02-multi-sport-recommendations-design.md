# Automatic multi-sport recommendations and strict historical combinations

Date: 2026-10-02
Status: user approved on 2026-10-02; implementation plans pending review. Not implemented or deployed.

## Requested outcome

Automatically discover upcoming football, basketball, tennis and ice-hockey events. The user does not supply team examples or choose which teams to investigate. Rank up to ten distinct events with a selected market and an adjacent evidence scorecard. Show estimated future probability separately from observed historical success. Keep the 2x/3x sections restricted to exact markets with a 100% historical record; no qualifying priced combination means no combination cards, including no unpriced fallback slips.

Retain the existing private Render application, Neon records, owner authentication and zero recurring cost requirement. No paid subscription, paid worker or automatic upgrade is authorized.

## Findings from this checkout

- The local database has 5,287 fixtures. Its fixture dates end on 2026-09-19. Its 12,468 saved odds have a latest receipt of 2026-09-19 04:48:54 UTC. These are the records previously imported to Neon. This does not establish the current live database state after any user-triggered refreshes.
- `accuracy_policy.analyze_evidence` already uses `historical_suggestions` without model/EV thresholds. Removing those thresholds again would not fix the active combination flow.
- `static/accuracy-policy.js` overrides the earlier Recommended Picks renderer and displays historical suggestions. It also renders unpriced two/three-selection slips under the payout tabs.
- `team_insights.evidence_for` restricts automatic discovery by football league scope. A manual SEARCH matchup is not an upcoming scheduled event and cannot be priced as a bet.
- Perfect records are mapped to exact market/line/team and relevant home/away role. Priced combinations additionally need a future scheduled fixture, fresh odds, one bookmaker and distinct events.
- Existing fixture/stat/model storage assumes football. Basketball points, tennis sets and hockey overtime cannot be placed in football goal fields.
- This local directory has no Git repository metadata. No GitHub CLI/token or connected GitHub tool is available. The target repository is CODE-404-BIT/MeVsMe; the known Render service is srv-davjrrvavr4c73carfn0. The public application URL and current deployed revision are not yet verified.

## Delivery structure

Deliver three independently testable parts in sequence: strict football evidence alignment and empty states; multi-sport ingestion/ranking and UI; live integration and acceptance. Each part gets an implementation plan after this design is reviewed. Completion of the first part must not be reported as completion of the whole request.

Keep the current football data path and introduce additive sport-aware tables/adapters for the other sports. Unify the view model and eligibility checks, not incompatible raw statistics. Avoid replacing the existing dashboard with a new hosted product.

## Discovery, refreshing and coverage

Default to the selected local calendar day with correct UTC boundaries. Discover participants from provider event feeds automatically. The sport selector defaults to All and supports the four requested sports. Ranking is global across eligible events, not ten events per sport. A user can expand the date window; events already underway or completed never enter upcoming picks.

On opening recommendations, show cached results immediately with their age and request a single authenticated refresh if stale. Use the existing guarded background-job pattern, persisted checkpoints and provider quotas. A refresh updates events, result history, prices and ranked output; the user does not enter team names. Concurrent browsers share the job rather than duplicating provider calls.

Show per-sport counts for events discovered, history-covered, probability-eligible, perfect-record markets and priced markets, with last successful refresh and failure reasons. Distinguish no scheduled games, missing credentials, quota exhausted, unavailable history and missing exact odds. Never label a partial scan as every worldwide game. Render sleep means scheduled unattended collection is not guaranteed; refreshing on access must work after restart.

## Source strategy and constraints

Retain API-Football and existing public football history adapters. For basketball and ice hockey, use separate API-Sports sport adapters and explicit enabled account credentials. Validate actual current-season and history access before marking either sport connected; do not assume the existing football entitlement covers them.

Use The Odds API's active-sport catalogue and event/odds feeds for supported competitions across all four sports, including tennis. Use its own API key, never the API-Football key. Its verified free plan currently supplies 500 credits per month and excludes historical odds. Cache, persist remaining credits, keep a reserve, and rotate eligible competitions fairly. Do not spend the entire month's quota on the first scan. Bookmaker region is Australia by default for this owner; expose coverage when a market has no supported bookmaker.

Tennis historical result ingestion is a release dependency, not an invented data source. Validate an accessible permitted results source and its actual schema/coverage before implementation of the tennis model. Attempts to read the previously known Jeff Sackmann repositories returned 404 and tennis-data.co.uk returned 403 in this environment. Do not claim those sources are operational or bypass access restrictions. The Odds API current odds alone are not enough to establish a historical perfect record or train a tennis model. If no free accessible history is available, report this as an unmet delivery requirement; a tennis tab showing only missing-data messages is not full completion.

Considered alternatives: a paid comprehensive feed exceeds the budget; undocumented public scoreboards have uncertain availability and settlement semantics. Prefer documented feeds and verified public history, acknowledging their quotas. Credentials are entered through provider/Render secret interfaces, never chat or source files.

## Identity and persistent data

New records include sport, competition, provider, provider event/participant IDs, UTC start time, event status, result settlement scope, source timestamps and ingestion time. Separate results from odds and frozen prediction snapshots. Keep canonical participant aliases explicit; ambiguous cross-provider matches are excluded rather than guessed from similar names. Tennis singles/doubles and ATP/WTA identities are separate; initial ranking supports singles.

Normalized markets include sport, market type, participant, line, period, overtime treatment and bookmaker. Basketball/hockey match winners including overtime are distinct from regulation winners. Tennis retirement/walkover outcomes are excluded unless the provider and bookmaker settlement rule are known to match. Unknown final scores, missing statistics and cancellations are not successes. Additive migrations preserve existing football records and IDs and support both local SQLite and PostgreSQL. Back up before production migration.

## Top-ten picks and scorecards

One best eligible market per event, up to ten events total. Never manufacture ten picks when coverage is insufficient. Use sport-specific outcome models: retain football's existing goal model; use chronological winner models for basketball/hockey; use a surface-aware singles winner model for tennis once suitable history is verified. Market-implied probabilities may be displayed separately with bookmaker margin removed when all outcomes exist, but never presented as a trained model's forecast.

Estimated win percentages require chronological out-of-sample evaluation with training restricted to information available before each event. Track calibration and Brier score against a sport/market baseline. Model promotion requires at least 100 held-out predictions, lower Brier score than baseline and a documented calibration check. Without that evidence show an explicitly labelled research estimate outside the ranked betting-picks list; do not silently promote it as a validated recommendation.

Rank eligible picks by validated probability, then history coverage, recency and a stable event-ID tie-break. Recent form is a feature and displayed evidence, not a substitute for opponent strength or validation. Avoid combining multiple markets from the same event to fill the list.

Each card shows sport/competition, participants, start time, selected market, estimated probability and model version, recent form, sample counts/date range, validation status, odds/bookmaker/timestamp when available, and an Evidence confidence /10 score. The confidence score describes sample coverage and freshness rather than loss risk or a second win probability. Preserve a visible statement that 100% historical success is not certainty about the next event. No guaranteed-safe claim.

## Strict 2x/3x rule

Use a shared structured evidence evaluator for Team Insights and combination selection. A qualifying record has hits == trials and trials >= 5 in a fixed predefined window (5, 10 or 20), uses only settled observations before the upcoming event, and matches the exact market/line/participant/venue and settlement scope. Show all scanned predefined windows for the selected market, not only its perfect window. Do not optimize arbitrary thresholds to manufacture 100%.

Keep the historical-combination rule independent of model probability/EV gates. Every displayed leg needs at least one qualifying perfect record and matching current bookmaker odds. Reject non-finite or <=1 prices, future timestamps, prices older than 24 hours and started/cancelled events. Revalidate at response time so cached analysis cannot retain expired eligibility. Latest observations older than 30 days remain explicitly marked stale, preserving current semantics rather than silently changing the user's historical rule.

Use distinct event identities and a single bookmaker. Preserve payout ranges 1.80-2.30 for 2x and 2.60-3.50 for 3x, up to four legs. These are payout targets, not selection counts. Keep a disclosed bounded search, stable ranking and per-sport participation in candidate pruning so the first busy league cannot consume the entire search. Never claim the bounded search exhausts all possible combinations.

Remove unpriced slip rendering and fallback API output from payout views. Historical evidence remains available in insights. An empty payout view contains only a reason and refresh status, not alternate bets. Do not assign 100% future or joint win probability to perfect-record combinations. Record exact evidence and odds snapshots for later settlement in a separate cohort from model-ranked picks.

## Verification and live acceptance

Regression cases: perfect evidence on a future priced fixture reaches combinations; one historical failure excludes that record; venue/line/participant mismatch excludes; search-only matchups do not become fixtures; missing/stale odds produce no cards; started events are removed without a manual reanalysis; timezone changes and provider duplicates do not duplicate picks.

Multi-sport cases: event ID collisions across sports, overtime vs regulation, tennis retirements and doubles, incomplete scores, missing history, unknown aliases, quota limits, malformed responses, failed-source isolation, temporal leakage, stable global top ten and no synthetic probability. Test live provider responses with non-secret fixtures as well as deterministic mocks; mocks alone do not prove live coverage.

Run applicable existing and new tests, PostgreSQL migration/restart checks, browser desktop/mobile checks and memory profiling for Render's free instance. Check login/CSRF protection on new routes. Check that top-ten and combination snapshots survive restart and that logging never prints provider secrets.

Before publication, connect authenticated GitHub access, fetch the live repository revision and reconcile differences with this checkout. Commit the tested changes to the branch Render actually deploys, verify the deployed revision and inspect startup logs. Confirm the public HTTPS application, authenticated refresh and per-sport data on the live service. Verify preserved imported record counts and no unpriced combination fallback. Do not mark the request complete without live verification of all four supported sports or an explicit user-approved scope change.

## References verified during design

- https://api-sports.io/sports/basketball
- https://api-sports.io/sports/hockey
- https://the-odds-api.com/
- https://the-odds-api.com/liveapi/guides/v4/index.html

## Review checkpoint

The user approved this written design on 2026-10-02. Implementation plans are the next checkpoint. No source code or live resources were changed while drafting it.
