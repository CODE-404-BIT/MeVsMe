# Zero-Cost Data Foundation — Subsystem Specification

## Purpose
Create a provider-agnostic ingestion and normalization layer using only free/open sources.

## Required providers
1. Football-Data.co.uk CSV adapter: historical/current-season match results, team match statistics and odds.
2. Football-Data.co.uk fixtures CSV adapter: upcoming fixtures plus available 1X2/totals/AH prices.
3. OpenLigaDB adapter: optional fixture/result fallback without authentication.
4. football-data.org adapter: optional free-token fixture/table source; disabled when no token is supplied.
5. Betfair delayed adapter interface: optional and disabled by default.

## Provenance rules
Every record must preserve source, source timestamp if available, fetch timestamp, competition and provider-native identifiers/names.

## Normalization rules
- Canonical team identities with alias table.
- Deterministic normalized string key for first-pass matching.
- Fuzzy matching cannot silently create mappings above an ambiguity threshold; ambiguous mappings are rejected/logged.
- Market rows normalize decimal odds, market line and market family.

## Storage
SQLite database under `data/app.db` by default. Raw downloaded files cached under `data/raw/<provider>/` for reproducibility.
