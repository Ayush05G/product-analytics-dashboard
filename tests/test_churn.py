"""Tests for the churn module: label/feature construction (hand-computed),
the too-short guard, the insight text, and that training plumbing runs.

Fixture (obs=2d, horizon=2d; ref = Jan 1 00:00, so obs=[Jan1,Jan3),
horizon=[Jan3,Jan5)):
  v10: Jan1 + Jan3        -> active in obs AND horizon -> returned (churn 0)
  v20: Jan1, Jan1, Jan2   -> obs only                  -> churn 1
  v30: Jan1               -> obs only                  -> churn 1
  v40: Jan3               -> horizon only              -> excluded
  v50: Jan10              -> spacer to extend span past horizon end
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.churn import FEATURES, churn_insight, make_churn_dataset, train_churn_models


@pytest.fixture
def events() -> pd.DataFrame:
    rows = [
        ("2021-01-01 06:00", 10, "view", 1),
        ("2021-01-03 06:00", 10, "view", 1),
        ("2021-01-01 00:00", 20, "view", 2),  # ref (earliest)
        ("2021-01-01 00:30", 20, "addtocart", 2),
        ("2021-01-02 00:00", 20, "view", 2),
        ("2021-01-01 12:00", 30, "view", 3),
        ("2021-01-03 08:00", 40, "view", 9),  # horizon only -> excluded
        ("2021-01-10 00:00", 50, "view", 10),  # extends span past Jan 5
    ]
    df = pd.DataFrame(rows, columns=["timestamp", "visitorid", "event", "itemid"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["event"] = df["event"].astype("category")
    return df


def test_labels_and_population(events):
    ds = make_churn_dataset(events, obs_days=2, horizon_days=2)
    assert set(ds.index) == {10, 20, 30}  # v40 (horizon-only) & v50 (spacer) excluded
    assert ds.loc[10, "churned"] == 0  # returned in horizon
    assert ds.loc[20, "churned"] == 1
    assert ds.loc[30, "churned"] == 1


def test_features_no_leakage(events):
    ds = make_churn_dataset(events, obs_days=2, horizon_days=2)
    b = ds.loc[20]
    assert b["num_events"] == 3
    assert b["num_views"] == 2
    assert b["num_carts"] == 1
    assert b["num_transactions"] == 0
    assert b["num_active_days"] == 2
    assert b["num_distinct_items"] == 1
    assert b["tenure_days"] == pytest.approx(1.0)  # Jan1 00:00 -> Jan2 00:00
    assert b["recency_days"] == pytest.approx(1.0)  # last obs event to obs_end
    assert b["events_per_active_day"] == pytest.approx(1.5)
    assert set(FEATURES).issubset(ds.columns)


def test_too_short_dataset_raises():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2021-01-01", "2021-01-02"], utc=True),
            "visitorid": [1, 2],
            "event": pd.Series(["view", "view"], dtype="category"),
            "itemid": [1, 2],
        }
    )
    with pytest.raises(ValueError):
        make_churn_dataset(df, obs_days=30, horizon_days=30)


def test_train_models_runs():
    rng = np.random.default_rng(0)
    n = 200
    recency = rng.uniform(0, 30, n)
    dataset = pd.DataFrame({f: rng.uniform(0, 5, n) for f in FEATURES})
    dataset["recency_days"] = recency
    # Deterministic, guaranteed-balanced label correlated with recency.
    dataset["churned"] = (recency > np.median(recency)).astype(int)

    res = train_churn_models(dataset)
    assert set(res["models"]) == {"logreg", "gbm"}
    assert res["n_visitors"] == n
    assert len(res["coefs"]) == len(FEATURES)
    for s in res["scores"].values():
        assert 0.0 <= s["roc_auc"] <= 1.0
        assert 0.0 <= s["pr_auc"] <= 1.0


def test_churn_insight_identifies_drivers():
    result = {
        "coefs": {f: 0.0 for f in FEATURES},
        "scores": {
            "logreg": {"roc_auc": 0.60, "pr_auc": 0.90},
            "gbm": {"roc_auc": 0.70, "pr_auc": 0.95},
        },
        "base_rate": 0.5,
    }
    result["coefs"]["recency_days"] = 0.9  # strongest churn signal
    result["coefs"]["num_active_days"] = -0.8  # strongest return signal

    msg = churn_insight(result)
    assert "recency days" in msg
    assert "num active days" in msg
    assert "0.700" in msg  # best (gbm) ROC-AUC
    assert "50%" in msg  # base rate
