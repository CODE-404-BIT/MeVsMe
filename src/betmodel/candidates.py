from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .value import expected_value


@dataclass(frozen=True)
class Candidate:
    fixture_id: int
    fixture_key: str
    market_key: str
    selection: str
    decimal_odds: float
    model_probability: float
    uncertainty: float
    data_quality: float
    pattern_strength: float
    price_timestamp: datetime
    fixture_resolved: bool = True
    line: float | None = None
    bookmaker: str | None = None
    model_version: str = 'poisson-baseline-v1'

    @property
    def ev(self) -> float:
        return expected_value(self.model_probability, self.decimal_odds)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str


def validate_candidate(
    candidate: Candidate,
    now: datetime,
    max_age: timedelta,
) -> ValidationResult:
    if not candidate.fixture_resolved:
        return ValidationResult(False, "fixture identity unresolved")
    if candidate.decimal_odds <= 1:
        return ValidationResult(False, "invalid decimal odds")
    if not 0 < candidate.model_probability < 1:
        return ValidationResult(False, "missing or invalid model probability")
    if candidate.price_timestamp > now:
        return ValidationResult(False, "price timestamp is in the future")
    if now - candidate.price_timestamp > max_age:
        return ValidationResult(False, "stale market price")
    if not 0 <= candidate.data_quality <= 1:
        return ValidationResult(False, "invalid data-quality score")
    if not 0 <= candidate.pattern_strength <= 1:
        return ValidationResult(False, "invalid pattern-strength score")
    return ValidationResult(True, "valid")


def quality_grade(candidate: Candidate) -> str:
    try:
        ev = candidate.ev
    except ValueError:
        return "DATA_INVALID"

    # Strong edge requires both enough value and sufficiently stable evidence.
    if ev >= 0.12 and candidate.data_quality >= 0.85 and candidate.uncertainty <= 0.05:
        return "A_STRONG_EDGE"
    if ev >= 0.05 and candidate.data_quality >= 0.70 and candidate.uncertainty <= 0.10:
        return "B_POSITIVE_EDGE"
    return "C_BEST_AVAILABLE"
