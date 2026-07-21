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

from src.metrics import cohort_retention, daily_active, funnel, kpis, top_items


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


@pytest.fixture
def events_with_cartless_buyer() -> pd.DataFrame:
    """8 events, 4 visitors — includes a buyer who never added to cart.

      v1: view + cart + transaction   (carted, then bought)
      v2: view + cart                 (carted, no purchase)
      v3: view + transaction          (bought WITHOUT ever carting)
      v4: view                        (viewed only)

    Hand-computed funnel:
      view        = 4 visitors
      addtocart   = 2 (v1, v2)      step 2/4 = 50%, progressed 2/4 = 50%
      transaction = 2 (v1, v3)      step 2/2 = 100% (naive, counts v3 who was
                                    never in the cart denominator)
                                    progressed = |{v1,v3} & {v1,v2}| = 1
                                    -> 1/2 = 50%
    This is the shape of the real RetailRocket gap (31.07% vs 28.04%), where
    9.8% of buyers have no add-to-cart event.
    """
    rows = [
        ("2021-01-04 10:00", 1, "view", 1),
        ("2021-01-04 11:00", 1, "addtocart", 1),
        ("2021-01-05 09:00", 1, "transaction", 1),
        ("2021-01-04 12:00", 2, "view", 2),
        ("2021-01-04 12:30", 2, "addtocart", 2),
        ("2021-01-04 13:00", 3, "view", 3),
        ("2021-01-04 13:30", 3, "transaction", 3),  # buys with no cart event
        ("2021-01-04 14:00", 4, "view", 4),
    ]
    df = pd.DataFrame(rows, columns=["timestamp", "visitorid", "event", "itemid"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["event"] = df["event"].astype("category")
    return df


def test_funnel_progression_excludes_buyer_who_never_carted(
    events_with_cartless_buyer,
):
    f = funnel(events_with_cartless_buyer).set_index("stage")

    assert f.loc["view", "visitors"] == 4
    assert f.loc["addtocart", "visitors"] == 2
    assert f.loc["transaction", "visitors"] == 2

    # Stage-count view: 2 buyers / 2 cart-adders = 100%, even though only one
    # of those buyers ever passed through the cart.
    assert f.loc["transaction", "step_conversion"] == pytest.approx(1.0)

    # Progression view: only v1 both carted and bought -> 1 / 2 cart-adders.
    assert f.loc["transaction", "visitors_progressed"] == 1
    assert f.loc["transaction", "step_conversion_progressed"] == pytest.approx(0.5)

    # view -> addtocart has no such gap: every carter also viewed.
    assert f.loc["addtocart", "visitors_progressed"] == 2
    assert f.loc["addtocart", "step_conversion_progressed"] == pytest.approx(0.5)
    assert f.loc["addtocart", "step_conversion"] == pytest.approx(0.5)

    # Top stage has no previous stage to progress from.
    assert pd.isna(f.loc["view", "visitors_progressed"])
    assert np.isnan(f.loc["view", "step_conversion_progressed"])


def test_funnel_progression_never_exceeds_stage_conversion(
    events, events_with_cartless_buyer
):
    """Progression counts are a subset of stage counts, in every fixture."""
    for df in (events, events_with_cartless_buyer):
        steps = funnel(df).iloc[1:]
        assert (steps["visitors_progressed"] <= steps["visitors"]).all()
        assert (
            steps["step_conversion_progressed"] <= steps["step_conversion"]
        ).all()
        assert steps["step_conversion_progressed"].between(0, 1).all()


def test_funnel_progression_matches_step_when_no_gap(events):
    """In the original fixture every buyer also carted, so the two rates agree."""
    f = funnel(events).set_index("stage")
    assert f.loc["transaction", "visitors_progressed"] == 1
    assert f.loc["transaction", "step_conversion_progressed"] == pytest.approx(
        f.loc["transaction", "step_conversion"]
    )


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


def test_daily_active_values(events):
    da = daily_active(events)
    assert len(da) == 3  # Jan 4, Jan 5, Jan 11
    assert da.tolist() == [2, 1, 1]  # {v1,v2}, {v1}, {v3}
    assert da.index.is_monotonic_increasing


def test_top_items_counts_and_order(events):
    items = top_items(events, n=10, min_views=1)
    # item 1: view+cart+txn; item 2: view+cart; item 3: view only.
    assert items.index[0] == 1  # sorted by purchases first
    assert items.loc[1, "views"] == 1
    assert items.loc[1, "carts"] == 1
    assert items.loc[1, "purchases"] == 1
    assert items.loc[1, "view_to_purchase"] == pytest.approx(1.0)
    assert items.loc[2, "purchases"] == 0
    assert items.loc[3, "carts"] == 0


def test_top_items_min_views_floor(events):
    items = top_items(events, n=10, min_views=50)
    # No item has 50+ views -> every conversion is NaN, counts unaffected.
    assert items["view_to_purchase"].isna().all()
    assert items["purchases"].sum() == 1
