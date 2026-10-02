from datetime import datetime, timedelta, timezone

from betmodel.candidates import Candidate, quality_grade, validate_candidate

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def base_candidate(**changes):
    values = dict(
        fixture_id=1,
        fixture_key="A-v-B",
        market_key="TOTAL_GOALS_OVER",
        selection="Over 2.5",
        decimal_odds=2.0,
        model_probability=0.58,
        uncertainty=0.04,
        data_quality=0.9,
        pattern_strength=0.8,
        price_timestamp=NOW - timedelta(minutes=2),
        fixture_resolved=True,
    )
    values.update(changes)
    return Candidate(**values)


def test_stale_price_is_invalid():
    candidate = base_candidate(price_timestamp=NOW - timedelta(hours=2))
    result = validate_candidate(candidate, NOW, max_age=timedelta(minutes=15))
    assert not result.valid
    assert "stale" in result.reason.lower()


def test_missing_fixture_identity_is_invalid():
    candidate = base_candidate(fixture_resolved=False)
    result = validate_candidate(candidate, NOW, max_age=timedelta(minutes=15))
    assert not result.valid


def test_small_positive_edge_is_best_available_grade():
    candidate = base_candidate(decimal_odds=1.75, model_probability=0.58)
    assert quality_grade(candidate) == "C_BEST_AVAILABLE"


def test_strong_positive_edge_with_good_data_is_a_grade():
    candidate = base_candidate(decimal_odds=2.0, model_probability=0.62, uncertainty=0.03, data_quality=0.95)
    assert quality_grade(candidate) == "A_STRONG_EDGE"
