# Evidence-based team insights and recommendations

The user has authorized implementation of the original researched-prediction goal and the Team Insights and Recommendations sidebar sections.

1. Preserve saved odds when quota prevents fetching a fixture. Test before fixing.
2. Add historical research service: public CSV archives for five major leagues and API-FOOTBALL completed league-season results for the selected day's competitions. Cache responses, track provenance, respect quotas, preserve 90-minute scores, and disclose unsupported coverage. No fuzzy team merges.
3. Add team search and historical summaries: individual form, venue form, H2H, pooled unique matches, and 5/10/20-match perfect records with dates, sample sizes and Bayesian intervals. Missing statistics excluded from denominators. Never describe records as guaranteed forecasts.
4. Add competition-specific goal predictions with minimum team/venue history; chronological validation against a training-only baseline. Rank supported priced selections by estimated probability, separately show EV and positive-edge qualification. Reject push/quarter lines until settlement-aware probability exists. Require fresh odds and future fixtures.
5. Add Team Insights and Recommendations sidebar views, search inputs, default daily fixtures, historical research button, source/freshness/coverage explanation and model-validation status. Include ranked picks only when evidence gates pass.
6. Test source parsing, quota/error handling, identity matching, deduplication, leakage, missing values, predictions/validation and browser interactions. Import actual public history, verify real database outputs and restart app.

Research: API-FOOTBALL pricing and beginner guide document free quotas, limited seasons and league-season /fixtures queries. datasets/football-datasets carries five 2025–26 league CSVs. These sources do not imply universal women's/youth/minor-league coverage. OpenFootball is a verified additional results source but not a mandatory scraper dependency.
