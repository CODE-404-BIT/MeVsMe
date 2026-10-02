# Zero-Cost Modelling & Pattern Engine — Subsystem Specification

## Purpose
Turn normalized historical team/market data into calibrated market probabilities using transparent statistical methods.

## Initial market families
- match result / goal totals / BTTS
- total/team corners
- total cards when source columns exist
- team shots and shots on target when source columns exist

## Pattern scanner
Compute historical hit counts and Bayesian-shrunk probabilities for rolling windows 5/10/20 and season/home/away splits.

## Model selection
Each model family must have at least one simple baseline. More complex alternatives are adopted only when walk-forward Brier/log-loss/calibration improves.

## Calibration
Use out-of-fold or walk-forward calibration. Calibration models must be versioned and never trained on future samples relative to an evaluated prediction.

## Outputs
Canonical `Prediction` records with probability, lower/upper uncertainty bounds, fair odds, model version and feature timestamp.
