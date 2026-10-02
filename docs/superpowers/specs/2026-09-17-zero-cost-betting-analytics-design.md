# Zero-Cost Betting Analytics System — Design Specification

**Date:** 2026-09-17

## Goal
Build a zero-cost, football-first analytics system that scans available matches and markets, estimates calibrated probabilities, detects perfect/near-perfect historical patterns, compares model probabilities with available market prices, constructs approximately 2x and 3x recommendations, emails a concise report, and tracks every prediction for later calibration and backtesting.

## Non-negotiable constraints

1. No paid subscriptions, paid APIs, paid hosting requirements, or paid LLM APIs.
2. The system must remain useful when only open/free data is available.
3. It must never invent unavailable odds, statistics, lineups, player status, or news.
4. It must distinguish `best available` from genuinely strong positive-edge recommendations.
5. Football is the first implemented sport, but core entities and recommendation interfaces must be sport-independent.
6. No automated bet placement in V1.
7. Email is the primary user interface in V1.
8. All probability values come from deterministic/statistical code. Any language model is explanation-only.
9. Player-prop recommendations are enabled only when a trustworthy free data source supplies the required player-level inputs; otherwise they remain unsupported rather than fabricated.

## Zero-cost technology stack

- Python 3.12+
- FastAPI only when/if a local API becomes useful; the first runnable version can be CLI-first
- SQLite for V1 persistence; schema designed so PostgreSQL can replace it later
- SQLAlchemy 2.x
- Pandas or Polars for tabular processing
- NumPy / SciPy / statsmodels / scikit-learn
- APScheduler or OS cron for local scheduling
- Jinja2 for deterministic HTML email templates
- SMTP through an existing email account for delivery
- pytest for tests
- Docker optional, not required to run locally
- Ollama-compatible local LLM endpoint optional for news summarisation/explanation; no paid cloud model is required

## Free data strategy

### Tier A — core sources

**Football-Data.co.uk**
- Free downloadable historical/current-season CSV files.
- Useful for results, half-time results, match odds, totals/Asian-handicap odds and team-level match statistics such as shots, shots on target, corners and cards for covered leagues.
- Also publishes a free fixtures/odds CSV, usually updated on a schedule rather than continuously.
- Primary source for backtesting and team-level market models.

**football-data.org free tier**
- Free-forever tier for 12 major competitions.
- Provides fixtures, schedules/results and league tables subject to free-tier delay/rate limits.
- Used only as an optional fixture/status source because deeper statistics and odds are paid.

**OpenLigaDB**
- Free unauthenticated API for available leagues/matches.
- Used as a secondary free fixture/result source where useful.

### Tier B — optional free-account live source

**API-FOOTBALL free plan**
- $0 account; no paid plan is required by this project.
- Current provider documentation advertises 100 requests/day and 10 requests/minute on the free tier.
- All endpoints are exposed on the free tier, while historical season depth is limited.
- Used optionally for today's fixtures and pre-match odds; the adapter records quota headers and stops odds calls at a configurable reserve.
- Unknown/ambiguous provider market names fail closed during canonicalisation.
- The system remains fully runnable without an API-FOOTBALL key.

### Tier C — optional free-account market validation

**Betfair Delayed API**
- Development/delayed key is free for private development/testing but requires a Betfair account.
- Data is delayed rather than truly live.
- Optional adapter for exchange prices, traded volume and market-depth validation.
- The system must run without this adapter.

### Tier D — open historical enrichment

**StatsBomb Open Data / other explicitly open datasets**
- Optional historical event-level enrichment for selected competitions.
- Used for research/model experimentation, not assumed to cover today's full slate.

### Explicitly excluded from core V1

- Sportradar paid products
- Sportmonks paid statistics/odds tiers
- Paid The Odds API plans
- Paid Betfair Live App Key
- Paid OpenAI API
- Unofficial scraper endpoints as mandatory production dependencies

Free APIs with small free quotas can later be implemented as optional adapters, but the core system cannot depend on them.

## Architectural layers

### Layer 1 — Data intelligence
- Fixtures
- Historical results
- Team-level shots / shots on target / corners / cards when available
- Historical bookmaker odds
- Optional delayed exchange prices
- Optional news/context feeds
- Data freshness and provenance metadata

### Layer 2 — Quantitative intelligence
- Team-strength ratings
- Goal model
- Corner model
- Card model
- Team-shot and team-SOT models
- Perfect/near-perfect pattern engine
- Probability calibration
- Uncertainty estimation
- Optional player models only when player data is trustworthy

### Layer 3 — Decision intelligence
- No-vig probability calculation
- Fair odds
- Expected value
- Minimum acceptable odds
- Data-quality gating
- Model-agreement scoring
- Combination generation
- Correlation handling
- 2x / 3x recommendation optimiser
- Portfolio/exposure controls

### Layer 4 — Language/delivery intelligence
- Deterministic explanation from verified metrics
- Optional local-LLM summarisation constrained to structured facts
- HTML/text email generation
- Result follow-up
- Performance report

## Canonical data model

### Core identity tables
- `sports`
- `competitions`
- `teams`
- `team_aliases`
- `players`
- `player_aliases`
- `fixtures`
- `provider_mappings`

### Match/stat tables
- `team_match_stats`
- `player_match_stats`
- `lineups`
- `availability_events`
- `context_events`

### Market tables
- `bookmakers`
- `market_definitions`
- `odds_snapshots`
- `exchange_snapshots`
- `bookmaker_market_rules`

Every odds record contains:
- fixture id
- bookmaker/source
- market type
- participant/selection
- line
- decimal odds
- source timestamp
- received timestamp
- market period
- settlement rule id where needed

### Prediction tables
- `model_versions`
- `predictions`
- `recommendations`
- `recommendation_legs`
- `results`
- `performance_snapshots`

Every prediction records its model version and data timestamp to prevent hindsight leakage.

## Market normalization

Canonical market keys include at least:

- `MATCH_HOME`, `MATCH_DRAW`, `MATCH_AWAY`
- `DOUBLE_CHANCE_*`
- `ASIAN_HANDICAP`
- `TOTAL_GOALS_OVER`, `TOTAL_GOALS_UNDER`
- `TEAM_GOALS_OVER`, `TEAM_GOALS_UNDER`
- `BTTS_YES`, `BTTS_NO`
- `TOTAL_CORNERS_OVER`, `TOTAL_CORNERS_UNDER`
- `TEAM_CORNERS_OVER`, `TEAM_CORNERS_UNDER`
- `TOTAL_CARDS_OVER`, `TOTAL_CARDS_UNDER`
- `TEAM_SHOTS_OVER`, `TEAM_SOT_OVER`
- player-market keys reserved for later free-data availability

Equivalent provider strings must map to these canonical keys before modelling/comparison.

## Perfect / near-perfect pattern engine

The pattern scanner searches for hit rates across:
- last 5
- last 10
- last 20
- season
- home only
- away only
- competition
- head-to-head
- similar-opponent buckets when enough data exists

Threshold buckets:
- 100%
- 95%+
- 90%+
- 85%+
- 80%+

Raw hit rate is never used directly as today's probability. A Bayesian/Beta-Binomial shrinkage estimate and uncertainty interval are produced so 5/5 does not become a 100% forecast.

## Model suite

### Goals
Start with independent Poisson and Dixon-Coles candidates, then choose/ensemble based on walk-forward out-of-sample calibration.

Outputs:
- scoreline distribution
- total-goal probabilities
- BTTS probability
- team-goal probabilities
- match result probabilities

### Corners
Use count models capable of overdispersion (Poisson baseline; negative-binomial candidate) and team/opponent rolling features.

### Cards
Use count model with team received/conceded rates and league baselines where available.

### Team shots / SOT
Use rolling team attacking/defensive rates and opponent-adjusted count models where the source provides these statistics.

### V1 daily count-market projection
For corners, cards, team shots and team SOT, V1 combines the target team's venue-specific production rate with the opponent's venue-specific concession rate, requiring minimum historical samples from both sides. The resulting count mean is converted to a Poisson over/under probability. Integer lines with push outcomes are skipped until explicit push-aware pricing is added. Missing statistics produce no candidate.

### Player props
Schema and interfaces exist in V1, but recommendations remain disabled until a trustworthy, free, current player-stat/lineup source is available.

## Probability and value calculations

For decimal odds `O` and calibrated model probability `p`:

- raw implied probability: `1 / O`
- fair odds: `1 / p`
- expected value: `p * O - 1`
- minimum acceptable odds for target EV `e`: `(1 + e) / p`

Multi-outcome markets use de-vigged market probabilities for comparison.

## Uncertainty and evidence

Each candidate stores separately:
- calibrated probability
- uncertainty interval
- data completeness score
- sample-size score
- pattern strength
- model disagreement
- market freshness
- optional exchange/liquidity score

A recommendation can be `best available` even if edge is weak, but the displayed quality label must reflect that.

## Combination engine

### Target ranges
- 2x target: decimal odds 1.80–2.30
- 3x target: decimal odds 2.60–3.50

The target is a constraint, not the objective. The optimiser maximises quality/expected value under risk and data-quality constraints.

### Cross-match combinations
Treat legs as independent only when they are from unrelated matches/teams and no obvious shared exposure exists.

### Same-match combinations
V1 should avoid unsupported SGM probability arithmetic. A same-match multi is recommended only after a joint simulator for the relevant market family exists. Until then, use cross-match combinations for the official 2x/3x email picks.

## Market validation

Without a paid live-odds feed, V1 market validation uses:
- free Football-Data.co.uk fixture odds when fresh enough
- historical open/closing odds in backtests
- optional Betfair delayed exchange adapter

Every price carries a freshness state. Stale prices may be used for modelling/reference but cannot be labelled executable/live.

## News/context

Zero-cost V1 does not make scraped news a hard dependency. Context adapters can ingest:
- RSS feeds
- official club announcements where machine-readable feeds are available
- free public news indexes such as GDELT
- manually supplied context

Any local LLM receives only retrieved source text plus structured metrics. It cannot alter numerical predictions.

## Recommendation quality states

- `A_STRONG_EDGE`: strong positive edge, good calibration, high data quality
- `B_POSITIVE_EDGE`: positive edge with moderate uncertainty
- `C_BEST_AVAILABLE`: best candidate available but small/uncertain edge
- `DATA_INVALID`: no recommendation because source data are stale, unresolved or missing

The system should normally return one 2x and one 3x combination when valid prices exist, but it must never fabricate a bet if data validation fails.

## Email format

Subject: `Daily Model Picks — YYYY-MM-DD`

Body sections:
1. Best 2x
2. Best 3x
3. Why selected
4. Main risks
5. Minimum acceptable odds
6. Data freshness / confidence
7. Matches and markets scanned
8. Previous-results summary when available

The email remains concise even if thousands of markets are processed.

## Backtesting and leakage controls

Walk-forward testing must recreate the information set available at each historical prediction timestamp.

Track:
- hit rate
- ROI
- Brier score
- log loss
- calibration curve
- closing-line value where closing prices exist
- maximum drawdown for simulated staking
- performance by league
- performance by market
- performance by quality grade

No historical result or closing odds may leak into features used for an earlier prediction timestamp.

## V1 success criteria

1. Runs locally for $0.
2. Downloads and normalizes free historical/current football data.
3. Trains/evaluates at least goals and corners models.
4. Scans 80/85/90/95/100% pattern buckets.
5. Computes calibrated probabilities, fair odds, EV and minimum acceptable odds.
6. Generates valid 2x and 3x cross-match combinations from available prices.
7. Produces a deterministic HTML/text email report.
8. Stores every prediction and result with model version.
9. Includes tests preventing leakage, invalid odds and fake 100% probabilities.
10. Operates without any paid key or subscription.
