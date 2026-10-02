# Multi-sport sources and release constraints

Status: local implementation in progress on 2026-10-02. No live four-sport coverage or deployment is claimed.

## Configured integrations

| Data | Provider | Render environment variable | Current verification |
|---|---|---|---|
| Football | Existing API-Football and public history paths | API_FOOTBALL_KEY | Existing integration, imported data ends September 19 in local copy |
| Basketball events/results | API-Sports v1 basketball `/games` | API_BASKETBALL_KEY | Adapter/schema/negative cases tested offline; owner account access not supplied |
| Ice-hockey events/results | API-Sports v1 hockey `/games` | API_HOCKEY_KEY | Adapter/schema/negative cases tested offline; owner account access not supplied |
| Winner odds/events | The Odds API v4 `/sports`, `/sports/{key}/odds` | ODDS_API_KEY | Complete-market parsing and persistent budget/cache tested offline; real account response verification outstanding |
| Tennis results/history | No verified permitted current automated source | None | Blocking tennis statistical recommendations |

Use only free plans. The owner must activate each API-Sports sport entitlement; a football key's validity does not prove another sport is enabled. Add values directly in Render Environment, never source/chat. Missing keys do not prevent startup or football browsing.

The Odds API's public plan page lists 500 free credits/month and no historical odds. The implementation reserves 50 monthly credits, caps requests at 14 credits/day, uses Australian bookmaker region and one winner market, and rotates one active competition per sport per refresh. Its sports catalogue costs zero provider credits. API-Sports retains 20 requests/day in reserve and reads remaining-quota headers. Actual coverage varies by account and season. Date feeds cache for 30 minutes; season histories for six hours. Requests run under the existing exclusive dashboard job guard.

Basketball/hockey results are full-game totals including overtime; three-way hockey regulation prices are not accepted as two-way winner prices. Unknown statuses, incomplete finals and missing identities are rejected. Odds-only event identities are matched to result-provider events only on exact participant names and nearby start times with the same sport/scope; ambiguous or unmatched identities never acquire invented history.

## Tennis access investigation

The primary tennis-data.co.uk data page was reachable by an authorized ordinary HTTP request on 2026-10-02 and reported weekly updates. Its current notice restricts automated bot/AI/data-training use. No dataset was downloaded or automated importer enabled from that source. Earlier web-tool reads returned 403, which alone did not establish the page's availability. The previously known upstream Jeff Sackmann repository URLs returned 404 during design research. An accessible archive ending in 2024 would not provide current form in October 2026.

Accordingly, tennis odds/events can be discovered but the app explicitly reports `history_source_required`. This is an incomplete requested capability, not a successful four-sport release. A permitted accessible current singles result feed (with player identity, event dates, surface, final scores and retirement/walkover semantics) is still needed.

## Live acceptance still required

Capture sanitized actual scheduled/final/odds responses for the configured accounts; verify current-season access, finality and names. Mock response tests do not establish live entitlements. Validate migrations against disposable PostgreSQL, profile on the 512 MiB Linux deployment shape, connect GitHub, reconcile the current remote revision, deploy and verify the public authenticated service. Do not repeat the original SQLite import into the populated Neon database.

References:

- https://api-sports.io/documentation/basketball/v1
- https://api-sports.io/documentation/hockey/v1
- https://the-odds-api.com/liveapi/guides/v4/index.html
- https://the-odds-api.com/
- https://www.tennis-data.co.uk/data.php
