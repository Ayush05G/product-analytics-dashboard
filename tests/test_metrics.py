"""Tests for the pure metric functions, with hand-computed expected values.

Fixture (6 events, 3 visitors):
  v1: view+cart Jan 4, transaction Jan 5   (converter; active 2 days)
  v2: view+cart Jan 4                       (1 day)
  v3: view      Jan 11 (next ISO week)      (1 day)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.metrics import cohort_retention, funnel, kpis


@pytest.fixture
def events() -> pd.DataFrame:
    rows = [
        ("2021-01-04 10:00", 1, "view", 1),
        ("2021-01-04 11:00", 1, "addtocart", 1),
        ("2021-01-05 09:00", 1, "transaction", 1),
        ("2021-01-04 12:00", 2, "view", 2),
        ("2021-01-04 12:30", 2, "addtocart", 2),
        ("2021-01-11 08:00", 3, "view", 3),
    ]
    df = pd.DataFrame(rows, columns=["timestamp", "visitorid", "event", "itemid"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["event"] = df["event"].astype("category")
    return df


def test_funnel_counts_and_rates(events):
    f = funnel(events).set_index("stage")
    assert f.loc["view", "visitors"] == 3
    assert f.loc["addtocart", "visitors"] == 2
    assert f.loc["transaction", "visitors"] == 1
    assert f.loc["transaction", "pct_of_top"] == pytest.approx(1 / 3)
    assert f.loc["addtocart", "step_conversion"] == pytest.approx(2 / 3)
    assert f.loc["transaction", "step_conversion"] == pytest.approx(0.5)
    assert np.isnan(f.loc["view", "step_conversion"])


def test_kpis_values(events):
    k = kpis(events)
    assert k["total_visitors"] == 3
    assert k["conversion_rate"] == pytest.approx(1 / 3)  # only v1 buys
    assert k["repeat_visitor_rate"] == pytest.approx(1 / 3)  # only v1 active 2+ days
    assert k["dau"] == pytest.approx(4 / 3)  # Jan4:2, Jan5:1, Jan11:1
    assert k["wau"] == pytest.approx(1.5)  # W1:{v1,v2}=2, W2:{v3}=1
    assert k["mau"] == pytest.approx(3.0)  # single month, 3 visitors
    assert k["dau"] <= k["wau"] <= k["mau"]


def test_cohort_retention_shape_and_values(events):
    c = cohort_retention(events, freq="W")
    assert (c[0] == 1.0).all()  # week-0 is 100% by construction

    week1_cohort = pd.Timestamp("2021-01-04")
    week2_cohort = pd.Timestamp("2021-01-11")
    # v1/v2 acquired in week 1, neither returns the next week -> 0%.
    assert c.loc[week1_cohort, 0] == pytest.approx(1.0)
    assert c.loc[week1_cohort, 1] == pytest.approx(0.0)
    # v3 acquired in week 2; no data for its week 1 -> NaN.
    assert c.loc[week2_cohort, 0] == pytest.approx(1.0)
    assert pd.isna(c.loc[week2_cohort, 1])
