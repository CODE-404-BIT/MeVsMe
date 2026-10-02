# Performance and model updates

The top-right **Live track record** panel separates model estimates from odds-only combinations. Counts are all-time unique combinations generated and saved before kickoff, not bets placed. Old cards are not backfilled as live predictions. The first snapshot is preserved when prices change or a model is updated.

Browse the 2x/3x tabs to save generated price combinations; select Model-backed combinations and analyze to save model estimates. The search remains bounded as described on each page. The target is combined decimal odds, not the number of legs.

Expand **Results, accuracy & model learning** for full wins/losses, partial/push outcomes, refunds, unit-stake return and Brier probability error. Win rate excludes partial/push/refund combinations. Return includes every settled combination, assumes one unit staked and is hypothetical. Many combinations share matches, so their results are not independent samples. No percentage appears until outcomes exist.

**Refresh results** checks saved fixture IDs regardless of the selected dashboard day. It uses at most eight provider calls per run and keeps a daily reserve of twenty requests. Missing keys or unavailable results leave predictions pending. While the dashboard page remains open with a configured key, result refresh is attempted every thirty minutes. It is not a background service when the browser/server is closed. Research also settles any results already loaded.

Goals settle against regulation full-time scores, including matches that subsequently go to extra time. Asian quarter-lines split into adjacent integer/half lines. Cancelled API fixtures need explicit provider cancellation evidence. Abandoned, postponed, awarded and walkover results do not automatically become refunds. Unsupported markets or absent required statistics stay pending. Bookmaker-specific overrides are not modeled.

**Evaluate model update** uses completed same-competition results. It chooses a shrinkage Poisson candidate on earlier development data and compares it against the incumbent and a historical-frequency baseline on a later holdout of at least forty matches. At least 120 competition matches are required, with whole dates kept in one partition. An accepted candidate must improve both Brier and log loss. Re-evaluation waits for forty fresh outcomes rather than repeatedly searching the same holdout. Research and result refresh also run this evaluation.

Accepted versions are persisted and used for subsequent supported goal forecasts; past snapshots remain unchanged. Models cannot substitute unknown-team averages and claim validation. Evaluation currently covers **Over 2.5 goals only**; it does not validate every market or an entire accumulator. Updates may be rejected. This mechanism measures proposed improvements; it cannot promise them.

Recommended Picks now explains exclusions per fixture. Price-only cards say **ODDS ONLY**, meaning their combined price is available but no model probability or EV is asserted. The performance counts and measured results never turn those cards into validated predictions.
