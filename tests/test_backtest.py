import pandas as pd

from betmodel.backtest import walk_forward_backtest


def test_walk_forward_never_trains_on_target_or_future_rows():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]),
        "signal": [0.2, 0.4, 0.6, 0.8, 0.7],
        "outcome": [0, 0, 1, 1, 1],
        "odds": [2.0, 2.0, 2.0, 2.0, 2.0],
    })

    def predict_fn(train, row):
        return {"probability": float(train["outcome"].mean()), "outcome": int(row["outcome"]), "odds": float(row["odds"])}

    report = walk_forward_backtest(frame, train_min=2, predict_fn=predict_fn)
    assert len(report.predictions) == 3
    assert all(p.training_max_date < p.fixture_date for p in report.predictions)
    assert 0 <= report.brier_score <= 1
    assert report.total_bets == 3
