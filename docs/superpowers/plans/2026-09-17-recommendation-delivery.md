# Zero-Cost Recommendation & Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn calibrated predictions plus free market prices into validated candidate bets, 2x/3x cross-match combinations, concise email output, and measurable result tracking.

**Architecture:** Pure functions calculate no-vig probabilities, fair odds, EV and minimum acceptable odds. A combination optimiser searches only validated cross-match legs in V1. Jinja2 renders deterministic email; SMTP is optional and previews always work locally.

**Tech Stack:** Python, NumPy, SQLAlchemy, Jinja2, smtplib, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-recommendation-delivery.md`

## Global Constraints
- 2x range 1.80–2.30; 3x range 2.60–3.50.
- Target odds are constraints, never the objective.
- No fabricated recommendation when price/data validation fails.
- Official V1 combinations are cross-match only unless a joint simulator is available.
- SMTP is optional; local HTML/text output is mandatory.

---

## File Structure
- `src/betmodel/value.py` — implied probability, no-vig, EV, MAO.
- `src/betmodel/candidates.py` — candidate validation/quality grade.
- `src/betmodel/optimizer.py` — combination generation and scoring.
- `src/betmodel/reporting.py` — report structures.
- `src/betmodel/templates/daily_email.html.j2` — HTML email.
- `src/betmodel/templates/daily_email.txt.j2` — text email.
- `src/betmodel/emailer.py` — preview/save/SMTP send.
- `src/betmodel/settlement.py` — result settlement and performance summary.
- Tests for each module.

### Task 1: Value mathematics

**Interfaces:**
- `implied_probability(decimal_odds: float) -> float`
- `devig(probabilities: list[float]) -> list[float]`
- `expected_value(p: float, decimal_odds: float) -> float`
- `minimum_acceptable_odds(p: float, min_ev: float) -> float`

- [ ] Write failing hand-calculation tests including `p=.60, min_ev=.05 -> 1.75`.
- [ ] Implement strict validation (`odds > 1`, `0 < p < 1`).
- [ ] Run tests.
- [ ] Commit.

### Task 2: Candidate validation and quality grading

**Interfaces:**
- `validate_candidate(candidate, now, max_age) -> ValidationResult`
- `quality_grade(candidate) -> Literal["A_STRONG_EDGE","B_POSITIVE_EDGE","C_BEST_AVAILABLE","DATA_INVALID"]`

- [ ] Write tests for stale odds, missing probability, unresolved fixture and valid small-edge candidate.
- [ ] Implement fail-closed validation and deterministic grades.
- [ ] Run tests.
- [ ] Commit.

### Task 3: 2x/3x cross-match optimiser

**Interfaces:**
- `optimize_combinations(candidates, min_odds, max_odds, max_legs=4) -> list[Combination]`
- Combination probability is product only after rejecting same-fixture legs.
- Score uses joint EV minus uncertainty/data-quality penalties.

- [ ] Write synthetic candidates where the highest raw odds are not the best EV combination.
- [ ] Assert same-fixture legs are rejected.
- [ ] Implement bounded combinations with pruning.
- [ ] Run tests.
- [ ] Commit.

### Task 4: Daily report renderer

**Interfaces:**
- `render_daily_report(report: DailyReport) -> RenderedEmail`
- Always includes best 2x, best 3x, reasons, risks, MAO, freshness and scan counts.

- [ ] Write snapshot-style tests against stable sample report.
- [ ] Implement Jinja2 HTML/text templates.
- [ ] Run tests.
- [ ] Commit.

### Task 5: Free SMTP delivery and local preview

**Interfaces:**
- `save_preview(rendered, output_dir) -> tuple[Path, Path]`
- `send_smtp(rendered, smtp_settings) -> None`

- [ ] Write tests ensuring preview files are created without credentials and SMTP is never attempted unless explicitly configured.
- [ ] Implement standard-library `smtplib` sender with TLS option.
- [ ] Run tests.
- [ ] Commit.

### Task 6: Settlement/performance tracking

**Interfaces:**
- `settle_recommendation(recommendation, final_stats) -> Settlement`
- `performance_summary(settlements) -> dict`

- [ ] Write tests for win/loss/void legs and decimal-odds return calculations.
- [ ] Implement combination settlement and ROI/hit-rate summaries.
- [ ] Run tests.
- [ ] Commit.

### Task 7: End-to-end daily command

**Files:**
- Modify: `src/betmodel/cli.py`
- Test: `tests/test_daily_pipeline.py`

**Interfaces:**
- CLI: `betmodel daily --date YYYY-MM-DD --preview-only`

- [ ] Build a fixture dataset with at least four matches and enough independent candidate legs for 2x/3x output.
- [ ] Write failing end-to-end test producing preview files.
- [ ] Implement daily orchestration from stored data -> model predictions -> candidates -> optimiser -> email preview.
- [ ] Run `pytest -q` and CLI smoke test.
- [ ] Commit.
