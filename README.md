# Daily Bet Model — Zero-Cost Football V1

A local, football-first analytics engine that uses free data, transparent statistical models, pattern scanning, value calculations, 2x/3x cross-match optimisation, HTML/text email reports, and optional SMTP delivery.

## Browser dashboard

For free cloud hosting with private login and persistent PostgreSQL, see [Cloud deployment](docs/cloud-deployment.md). Deployment source is prepared; account setup and publication are still required.

### Historical suggestions and current results

- **Matches of the Day:** European top domestic divisions plus England's Championship. Fixtures without history for both teams are hidden, except European top-division fixtures. Championship fixtures need history. Refresh fixtures to resolve older entries missing country metadata. Use the local/UTC date selector deliberately.
- **Research & load history:** refreshes 2026–27 (automatically advances each July) completed-result files for 12 divisions, alongside the existing archives and quota-limited API research. The current-season cache expires after six hours. Latest published result dates and source failures are visible; coverage is not guaranteed for every club.
- **Recommended Picks:** matching 100% historical records with at least five observations, without model or EV gates. Each suggestion shows its sample and dates. Home/away records must match the upcoming team's venue. Records older than 30 days are flagged.
- **2× / 3×:** exactly matching markets with fresh saved odds, separate fixtures and one bookmaker. Target prices are 1.80–2.30 and 2.60–3.50. The bounded search checks up to 32 selections per bookmaker and four legs, displaying up to 20 combinations per target. Without matching prices, two- and three-selection historical slips still appear, labeled Odds needed — payout unconfirmed. Selection count is not payout. Unpriced drafts are excluded from priced performance tracking.
- **Evidence /10:** sample coverage (up to 7 points) plus recency (up to 3), capped at 9.9. It is not a future win probability or a safety guarantee. Historical suggestions have no assigned forecast probability or EV.
- **Prediction History / top-right record:** choose Historical suggestions to see its saved combinations and settled win rate separately from legacy model and odds-only records. Only verified final results/statistics settle a leg; missing data stays pending.

Double-click **Launch Dashboard.vbs**, then press **Ctrl+F5** if the browser has older scripts. The local dashboard is at **http://127.0.0.1:8765**. Add your API key in **API Settings** for fresh fixtures and odds. The key lasts only for the server session, so restarting requires re-entry. Click **Research & load history** for current results, then the recommendation or combination tab.

100% describes the observed sample, not a guaranteed next result. Injuries, lineups, weather and news are not part of this historical-pattern selection method. The separate command-line model remains available below.

## Cost rule

The required recurring cost is **$0**. The core system runs from open data and local software. API-FOOTBALL is optional and uses its $0 free account; no paid API, cloud hosting, paid LLM, or paid email service is required.

## What V1 does

- Imports free historical/current CSV data from Football-Data.co.uk.
- Optionally syncs today's fixtures and pre-match odds from API-FOOTBALL's free tier.
- Normalises provider market wording into canonical markets and drops unknown/ambiguous markets.
- Models match result, Over/Under 2.5, BTTS, total/team corners, total/team cards, team shots, and team shots on target when the required history and matching odds exist.
- Scans team, opponent and H2H 80/85/90/95/100% historical patterns with Bayesian shrinkage so a past 100% record is never treated as a 100% future probability.
- Calculates model probability, fair odds, expected value, minimum acceptable odds, uncertainty and data quality.
- Builds cross-match combinations in the configured ~2x (1.80–2.30) and ~3x (2.60–3.50) ranges.
- Saves deterministic HTML/text email previews and can send them through ordinary SMTP.
- Stores predictions, model versions, recommendations and outcomes for later calibration/backtesting.

## Important V1 limits

- Player props and official same-game-multi pricing are **not enabled yet** unless a trustworthy free player-level data/odds path is implemented. The engine does not fabricate them.
- Same-match legs are excluded from the official 2x/3x optimiser until a joint simulator for those market families is implemented.
- API-FOOTBALL's free plan is quota-limited; the sync command preserves a configurable reserve.
- Whole-number count lines that can push (for example Over 8.0 corners) are skipped in the V1 count-market probability path rather than incorrectly treated as simple win/loss outcomes.

## Requirements

- Python 3.12+
- Internet access only when downloading/syncing free data
- An API-FOOTBALL free key only if you want the optional live fixture/odds sync
- An SMTP-capable email account only if you want automatic email delivery

## Install

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## 1. Initialise the local database

```bash
betmodel init-db --root .
```

## 2. Load historical data for model training

Example: English Premier League 2026-27 (`E0`, archive code `2627`):

```bash
betmodel fetch-season --season-code 2627 --season 2026-27 --league E0 --root .
```

Repeat for any free Football-Data.co.uk leagues you want in the historical database.

You can also fetch the current Football-Data.co.uk fixtures file:

```bash
betmodel fetch-latest --season 2026-27 --root .
```

## 3. Optional: enable free API-FOOTBALL live sync

Create a free API-FOOTBALL account/key at:

`https://www.api-football.com/`

The provider currently advertises a $0 plan with 100 requests/day, 10 requests/minute, and access to fixtures, lineups, injuries, statistics and odds. Free-season history is limited, so Football-Data.co.uk remains the main backtesting source.

PowerShell for the current shell:

```powershell
$env:API_FOOTBALL_KEY="YOUR_FREE_KEY"
```

Then sync a date:

```bash
betmodel sync-api-football --date 2026-09-17 --root . --quota-reserve 20
```

The command fetches the date slate once, then stops requesting odds when the free daily quota reaches the reserve.

## 4. Generate today's report locally

```bash
betmodel daily --date 2026-09-17 --root . --max-price-age-hours 24
```

The HTML and text previews are written under `data/previews/` by default.

## 5. Send the report by email for free

The program uses standard SMTP. For Gmail, a Google app password can be used when the account is configured for it; any other SMTP provider is also acceptable.

PowerShell example:

```powershell
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_SENDER="youraddress@gmail.com"
$env:SMTP_RECIPIENT="youraddress@gmail.com"
$env:SMTP_USERNAME="youraddress@gmail.com"
$env:SMTP_PASSWORD="YOUR_APP_PASSWORD"
$env:SMTP_TLS="true"
```

Then:

```bash
betmodel daily --date 2026-09-17 --root . --send
```

Without `--send`, SMTP variables are not required.

## 6. Automate it on Windows without paid hosting

Use **Windows Task Scheduler** and create two daily tasks (or one task with two actions):

1. Sync the live free data before the report:

```text
Program: <project>\.venv\Scripts\betmodel.exe
Arguments: sync-api-football --date YYYY-MM-DD --root <project> --quota-reserve 20
```

2. Run the model and email it:

```text
Program: <project>\.venv\Scripts\betmodel.exe
Arguments: daily --date YYYY-MM-DD --root <project> --send --max-price-age-hours 24
```

For a real scheduled task, use a short PowerShell wrapper to substitute the current local date (`Get-Date -Format yyyy-MM-dd`) into both commands. Keep API/SMTP secrets in the user environment rather than placing them directly in the Task Scheduler arguments.

## Commands

```bash
betmodel --help
betmodel init-db --help
betmodel fetch-season --help
betmodel fetch-latest --help
betmodel sync-api-football --help
betmodel daily --help
```

## Testing

From a source checkout:

```bash
PYTHONPATH=src python -m pytest -q
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m pytest -q
```

## Data sources

- Football-Data.co.uk: `https://www.football-data.co.uk/`
- API-FOOTBALL: `https://www.api-football.com/`
- football-data.org: optional fixture source
- OpenLigaDB: optional fixture source

No scraper-only or paid provider is required for V1.

## Live performance and model learning

### Historical dashboard selection

The dashboard now uses the historical-pattern workflow described above. Legacy command-line model behavior remains separate. Historical suggestions are tracked in their own cohort and are not assigned forecast probabilities.
