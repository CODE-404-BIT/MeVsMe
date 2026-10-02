# Zero-Cost Recommendation & Delivery — Subsystem Specification

## Purpose
Compare model probabilities with available prices, build 2x/3x combinations, produce concise emails and track outcomes.

## Candidate validation
Reject candidates with invalid/zero odds, unresolved fixture/team identity, stale execution price beyond configured threshold, or unavailable model probability.

## Recommendation optimisation
- Build cross-match combinations first.
- 2x total odds range 1.80–2.30.
- 3x total odds range 2.60–3.50.
- Score combinations using expected value, model uncertainty, data quality, pattern evidence and exposure diversity.
- Never add legs merely to reach target odds.

## Email
Use local Jinja2 templates. Send through SMTP only when credentials are configured; otherwise always save preview HTML/text locally.

## Follow-up
Settle stored recommendations from imported final results and generate daily/rolling accuracy, ROI and calibration summaries.
