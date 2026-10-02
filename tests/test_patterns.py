import pandas as pd
from betmodel.patterns import beta_posterior_mean, beta_interval, scan_patterns


def test_perfect_historical_record_is_shrunk_below_one():
    p5 = beta_posterior_mean(5, 5)
    p20 = beta_posterior_mean(20, 20)
    assert 0 < p5 < p20 < 1


def test_beta_interval_contains_posterior_mean():
    mean = beta_posterior_mean(9, 10)
    low, high = beta_interval(9, 10)
    assert 0 <= low < mean < high <= 1


def test_scan_patterns_reports_recent_windows_without_using_future_rows():
    frame = pd.DataFrame({
        "date": pd.to_datetime([f"2026-01-{d:02d}" for d in range(1, 7)]),
        "value": [1, 1, 1, 1, 0, 1],
    })
    results = scan_patterns(frame, lambda row: bool(row["value"]), windows=(5,))
    last = results[-1]
    assert last.trials == 5
    assert last.hits == 4
    assert last.raw_hit_rate == 0.8
