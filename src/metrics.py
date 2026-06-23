"""Pure metric functions over the cleaned clickstream.

No Streamlit imports here (CLAUDE.md): every function takes a DataFrame and
returns a DataFrame / dict so the logic stays UI-free and testable. The same
funnel / cohort / KPI logic generalizes to any event stream.

Expected input is the DataFrame returned by ``data_load.load_events``:
columns ``timestamp`` (UTC datetime), ``visitorid`` (int), ``event``
(view | addtocart | transaction), ``itemid`` (int).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FUNNEL_STAGES: tuple[str, ...] = ("view", "addtocart", "transaction")


def funnel(df: pd.DataFrame) -> pd.DataFrame:
    """View -> addtocart -> transaction funnel, at the visitor level.

    A visitor "reaches" a stage if they performed that event at least once
    anywhere in the window (not strictly ordered per-visit). Returns one row
    per stage with:

    - ``visitors``        : distinct visitors who reached the stage
    - ``pct_of_top``      : visitors / stage-1 visitors (overall funnel %)
    - ``step_conversion`` : visitors / previous-stage visitors (per-step %)

    Note: counts are not guaranteed monotonic in theory (a cart with no prior
    recorded view is possible), so ``step_conversion`` can exceed 1.0; in the
    RetailRocket data it does not. We surface the raw numbers rather than
    forcing monotonicity, so the metric stays honest.
    """
    counts = {
        stage: df.loc[df["event"] == stage, "visitorid"].nunique()
        for stage in FUNNEL_STAGES
    }
    top = counts[FUNNEL_STAGES[0]]

    rows = []
    prev: int | None = None
    for stage in FUNNEL_STAGES:
        n = counts[stage]
        rows.append(
            {
                "stage": stage,
                "visitors": n,
                "pct_of_top": (n / top) if top else float("nan"),
                "step_conversion": (n / prev) if prev else float("nan"),
            }
        )
        prev = n

    return pd.DataFrame(rows)


def cohort_retention(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Weekly acquisition-cohort retention.

    A visitor's cohort is the period (default weekly, ISO weeks) of their
    *first* event. They are "retained" in a later period if they have **any**
    event in that period. Returns a cohort x period-offset matrix of retention
    rates (week 0 == 1.0 by construction), indexed by cohort start date with
    integer column offsets (0, 1, 2, ...).

    Observable-but-empty cells are 0.0 (a genuine 0% retention); only cells
    that fall beyond the data's last period for a given cohort are left NaN
    (not observed yet) — so a real zero is never confused with missing data.

    Pass ``freq="M"`` for monthly cohorts, etc. (any pandas period alias).
    """
    # Drop tz before to_period (periods are tz-naive); data is UTC so week/
    # month boundaries are unaffected. Avoids a noisy UserWarning.
    period = df["timestamp"].dt.tz_localize(None).dt.to_period(freq)
    first_period = period.groupby(df["visitorid"]).transform("min")

    # Integer offset of each event's period from the visitor's cohort period.
    offset = (period - first_period).apply(lambda x: x.n)

    work = pd.DataFrame(
        {
            "visitorid": df["visitorid"].to_numpy(),
            "cohort": first_period.array,  # keep as Period for the horizon math
            "offset": offset.to_numpy(),
        }
    )

    # Distinct visitors active per (cohort, offset).
    counts = (
        work.groupby(["cohort", "offset"])["visitorid"].nunique().unstack("offset")
    )

    # Each cohort is only observable out to (last data period - cohort period)
    # offsets. Span columns to that full horizon, fill observable empties with
    # 0, and leave still-unobservable future cells as NaN.
    last_period = period.max()
    cohorts = counts.index  # PeriodIndex
    horizon = np.array([(last_period - p).n for p in cohorts])
    max_off = int(horizon.max())

    counts = counts.reindex(columns=range(max_off + 1)).astype(float)
    offsets = np.arange(max_off + 1)
    observable = offsets[None, :] <= horizon[:, None]
    counts = counts.where(observable, np.nan)  # mask the future
    counts = counts.mask(observable & counts.isna(), 0.0)  # observed zeros -> 0

    cohort_size = counts[0]  # offset 0 == every visitor in the cohort
    retention = counts.div(cohort_size, axis=0)
    retention.index = cohorts.to_timestamp()
    retention.index.name = "cohort"
    retention.columns.name = "offset"
    return retention


def kpis(df: pd.DataFrame) -> dict[str, float | int]:
    """Headline KPIs for the overview section.

    - ``dau`` / ``wau`` / ``mau`` : mean distinct active visitors per
      day / ISO-week / month across the observed window.
    - ``conversion_rate``         : visitors with >= 1 transaction / all visitors.
    - ``repeat_visitor_rate``     : visitors active on >= 2 distinct calendar
      days / all visitors.
    - ``total_visitors``          : distinct visitors (denominator, for context).
    """
    ts = df["timestamp"]
    day = ts.dt.floor("D")
    ts_naive = ts.dt.tz_localize(None)  # tz-naive for period bucketing

    dau = df.groupby(day)["visitorid"].nunique().mean()
    wau = df.groupby(ts_naive.dt.to_period("W"))["visitorid"].nunique().mean()
    mau = df.groupby(ts_naive.dt.to_period("M"))["visitorid"].nunique().mean()

    total_visitors = df["visitorid"].nunique()
    converters = df.loc[df["event"] == "transaction", "visitorid"].nunique()

    # Distinct active days per visitor; repeat = active on 2+ days.
    days_per_visitor = df.assign(day=day).groupby("visitorid")["day"].nunique()
    repeat_visitors = int((days_per_visitor >= 2).sum())

    return {
        "total_visitors": total_visitors,
        "dau": float(dau),
        "wau": float(wau),
        "mau": float(mau),
        "conversion_rate": converters / total_visitors,
        "repeat_visitor_rate": repeat_visitors / total_visitors,
    }


def _print_verification(df: pd.DataFrame) -> None:
    """Run all three metrics on real data and print numbers to eyeball,
    with internal-consistency assertions."""
    print("\n=== FUNNEL (visitor-level) ===")
    f = funnel(df)
    for _, r in f.iterrows():
        print(
            f"  {r['stage']:<12} {int(r['visitors']):>9,}"
            f"  | of top {r['pct_of_top']:6.2%}"
            f"  | step {r['step_conversion'] if pd.notna(r['step_conversion']) else float('nan'):6.2%}"
        )
    # Funnel stages cannot exceed total visitor count.
    total_v = df["visitorid"].nunique()
    assert f["visitors"].max() <= total_v, "a funnel stage exceeds total visitors"

    print("\n=== KPIs ===")
    k = kpis(df)
    print(f"  total_visitors      : {k['total_visitors']:,}")
    print(f"  DAU (avg/day)       : {k['dau']:,.0f}")
    print(f"  WAU (avg/week)      : {k['wau']:,.0f}")
    print(f"  MAU (avg/month)     : {k['mau']:,.0f}")
    print(f"  conversion_rate     : {k['conversion_rate']:.4%}")
    print(f"  repeat_visitor_rate : {k['repeat_visitor_rate']:.4%}")
    assert 0 <= k["conversion_rate"] <= 1
    assert 0 <= k["repeat_visitor_rate"] <= 1
    assert k["dau"] <= k["wau"] <= k["mau"], "DAU<=WAU<=MAU expected"

    print("\n=== WEEKLY COHORT RETENTION (first 6 cohorts x 6 weeks) ===")
    c = cohort_retention(df, freq="W")
    shown = c.iloc[:6, :6]
    with pd.option_context("display.float_format", lambda v: f"{v:5.1%}"):
        print(shown.to_string())
    # Week-0 retention is 100% by construction for every cohort.
    assert (c[0] == 1.0).all(), "week-0 retention must be 100%"
    print("\nAll internal-consistency checks passed.")


if __name__ == "__main__":
    from data_load import load_events

    _print_verification(load_events())
