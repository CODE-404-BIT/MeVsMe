import pandas as pd
import pytest
from scipy.stats import poisson

from betmodel.models_counts import fit_count_model


def test_poisson_count_model_tail_probability():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
        "team": ["A", "A", "B", "B"],
        "corners": [4, 4, 4, 4],
    })
    model = fit_count_model(frame, "corners", cutoff=pd.Timestamp("2026-02-01"), distribution="poisson")
    assert model.prob_over(3.5, {"team": "A"}) == pytest.approx(1 - poisson.cdf(3, 4.0))


def test_count_model_rejects_missing_stat_column():
    frame = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "team": ["A"]})
    with pytest.raises(ValueError, match="corners"):
        fit_count_model(frame, "corners", cutoff=pd.Timestamp("2026-02-01"))
