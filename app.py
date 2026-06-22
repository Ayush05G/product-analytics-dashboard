"""Product Analytics Dashboard — Streamlit UI.

UI only: all metric logic lives in src/ (pure pandas, testable). This module
wires the cleaned clickstream into cached aggregations and renders three
sections — Overview (KPIs), Funnel, and Cohort Retention — each surfacing a
plain-English insight derived from the data, not just a chart.
"""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from src.churn import churn_insight, make_churn_dataset, train_churn_models
from src.data_load import load_events, sanity_report
from src.metrics import FUNNEL_STAGES, cohort_retention, funnel, kpis

st.set_page_config(page_title="Product Analytics Dashboard", layout="wide")


# --- Cached data layer ----------------------------------------------------
# Cached metric functions key on the (start, end) date range — cheap to hash —
# and pull the full cached DataFrame internally, so the 2.7M-row frame is never
# re-hashed as a cache key on every rerun.


@st.cache_data(show_spinner="Loading clickstream…")
def get_data():
    return load_events()


@st.cache_data
def get_bounds() -> tuple[date, date]:
    """Min/max calendar dates in the dataset, for the date-range picker."""
    s = sanity_report(get_data())
    return s["date_min"].date(), s["date_max"].date()


def _filter(start: date, end: date):
    """Rows whose event date falls within [start, end], inclusive."""
    df = get_data()
    d = df["timestamp"].dt.date
    return df[(d >= start) & (d <= end)]


@st.cache_data(show_spinner="Computing KPIs…")
def get_kpis(start: date, end: date):
    return kpis(_filter(start, end))


@st.cache_data(show_spinner="Building funnel…")
def get_funnel(start: date, end: date):
    return funnel(_filter(start, end))


@st.cache_data(show_spinner="Building cohorts…")
def get_cohorts(start: date, end: date):
    return cohort_retention(_filter(start, end), freq="W")


@st.cache_data
def get_sanity(start: date, end: date):
    return sanity_report(_filter(start, end))


@st.cache_data(show_spinner="Training churn model…")
def get_churn():
    """Train on the full dataset — the obs/horizon windows are intrinsic to the
    churn definition and independent of the sidebar date filter."""
    return train_churn_models(make_churn_dataset(get_data()))


# --- Insight helpers (plain English, computed from the data) --------------


def funnel_insight(f) -> str:
    """Name the biggest leak in the funnel from the step-conversion rates."""
    steps = f.iloc[1:]  # rows after the top stage have a step_conversion
    worst = steps.loc[steps["step_conversion"].idxmin()]
    prev_stage = FUNNEL_STAGES[FUNNEL_STAGES.index(worst["stage"]) - 1]
    drop = 1 - worst["step_conversion"]
    overall = f.iloc[-1]["pct_of_top"]
    return (
        f"The biggest leak is **{prev_stage} → {worst['stage']}**: "
        f"**{drop:.1%}** of visitors who reach *{prev_stage}* never "
        f"continue to *{worst['stage']}*. End to end, only "
        f"**{overall:.2%}** of visitors who view an item go on to purchase."
    )


def kpi_insight(k) -> str:
    return (
        f"Acquisition is broad — about **{k['mau']:,.0f}** monthly active "
        f"visitors — but engagement is shallow: only **{k['repeat_visitor_rate']:.1%}** "
        f"return on a second day, and **{k['conversion_rate']:.2%}** ever purchase. "
        f"Repeat engagement, not traffic, is the main growth lever."
    )


def cohort_insight(c) -> str:
    """Average week-1 retention across cohorts (excluding the final, partial
    cohort that has had no chance to return)."""
    if 1 not in c.columns:
        return "Not enough weeks of data to measure return behavior yet."
    week1 = c[1].dropna()
    avg = week1.mean()
    best_cohort = week1.idxmax()
    return (
        f"On average only **{avg:.1%}** of a week's new visitors come back the "
        f"following week — retention drops off sharply after acquisition. The "
        f"strongest start was the cohort beginning **{best_cohort:%b %d, %Y}** "
        f"at **{week1.max():.1%}** week-1 return."
    )


# --- Rendering ------------------------------------------------------------


def render_overview(start: date, end: date) -> None:
    k = get_kpis(start, end)
    s = get_sanity(start, end)
    st.subheader("Overview")

    c1, c2, c3 = st.columns(3)
    c1.metric("Avg DAU", f"{k['dau']:,.0f}")
    c2.metric("Avg WAU", f"{k['wau']:,.0f}")
    c3.metric("Avg MAU", f"{k['mau']:,.0f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Total visitors", f"{k['total_visitors']:,}")
    c5.metric("Conversion rate", f"{k['conversion_rate']:.2%}")
    c6.metric("Repeat-visitor rate", f"{k['repeat_visitor_rate']:.1%}")

    st.info(kpi_insight(k))
    st.caption(
        f"{s['total_rows']:,} events · {s['date_min']:%b %d, %Y} – "
        f"{s['date_max']:%b %d, %Y}"
    )


def render_funnel(start: date, end: date) -> None:
    f = get_funnel(start, end)
    st.subheader("Conversion Funnel")

    fig = go.Figure(
        go.Funnel(
            y=f["stage"].str.capitalize(),
            x=f["visitors"],
            textinfo="value+percent initial",
        )
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=380)
    st.plotly_chart(fig, use_container_width=True)

    st.info(funnel_insight(f))
    st.caption(
        "Visitor-level: a visitor counts at a stage if they performed that "
        "event at least once (not strictly per-session ordered)."
    )


def render_retention(start: date, end: date) -> None:
    c = get_cohorts(start, end)
    st.subheader("Weekly Cohort Retention")

    z = (c * 100).round(1)
    fig = go.Figure(
        go.Heatmap(
            z=z.values,
            x=[f"W{col}" for col in z.columns],
            y=[d.strftime("%b %d") for d in z.index],
            colorscale="Blues",
            zmin=0,
            zmax=20,  # cap so week-0 (100%) doesn't flatten the gradient
            colorbar=dict(title="% retained"),
            hovertemplate="Cohort %{y} · %{x}<br>%{z}% retained<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=480,
        yaxis=dict(title="Acquisition week", autorange="reversed"),
        xaxis=dict(title="Weeks since first visit"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.info(cohort_insight(c))
    st.caption(
        "Each row is the week a visitor first appeared; cells show the share "
        "active again N weeks later (any event = retained)."
    )


def _date_range_picker() -> tuple[date, date]:
    """Sidebar date-range control; returns the selected (start, end).

    Falls back to the full dataset range while the user is mid-selection
    (st.date_input yields a 1-tuple between the two clicks)."""
    lo, hi = get_bounds()
    st.sidebar.header("Filters")
    picked = st.sidebar.date_input(
        "Date range",
        value=(lo, hi),
        min_value=lo,
        max_value=hi,
        format="YYYY-MM-DD",
    )
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        start, end = picked
    else:  # mid-selection (single date) — hold the full range until complete
        start, end = lo, hi
    if start > end:
        start, end = end, start
    st.sidebar.caption(f"Showing {start:%b %d, %Y} – {end:%b %d, %Y}")
    return start, end


def render_churn() -> None:
    res = get_churn()
    st.subheader("Churn (Return-Prediction) Model")

    scores = res["scores"]
    best = max(scores, key=lambda m: scores[m]["roc_auc"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Visitors modeled", f"{res['n_visitors']:,}")
    c2.metric("Churn base rate", f"{res['base_rate']:.1%}")
    c3.metric("ROC-AUC (LogReg)", f"{scores['logreg']['roc_auc']:.3f}")
    c4.metric(
        "ROC-AUC (GBM)",
        f"{scores['gbm']['roc_auc']:.3f}",
        delta=f"best: {best}",
        delta_color="off",
    )

    # Standardized logistic coefficients: comparable across features and the
    # basis for the insight. Positive = pushes toward churn, negative = return.
    coefs = res["coefs"]
    items = sorted(coefs.items(), key=lambda kv: kv[1])
    labels = [k.replace("_", " ") for k, _ in items]
    values = [v for _, v in items]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=["#c0392b" if v > 0 else "#2980b9" for v in values],
            hovertemplate="%{y}: %{x:+.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=420,
        title="What predicts churn — standardized logistic coefficients",
        xaxis_title="← predicts return     coefficient     predicts churn →",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.info(churn_insight(res))
    st.caption(
        "Churn = active in the first 30 days but no event in the following 30. "
        "Features use the first window only (no leakage). PR-AUC is high "
        f"({scores[best]['pr_auc']:.2f}) mainly because ~{res['base_rate']:.0%} "
        "of visitors churn — ROC-AUC is the honest headline. Uses the full "
        "dataset; the sidebar date filter does not apply here."
    )


def main() -> None:
    st.title("Product Analytics Dashboard")
    st.caption("RetailRocket clickstream — funnel, retention, and KPIs.")

    start, end = _date_range_picker()

    if get_sanity(start, end)["total_rows"] == 0:
        st.warning("No events in the selected date range. Widen the range.")
        return

    overview, funnel_tab, retention_tab, churn_tab = st.tabs(
        ["Overview", "Funnel", "Retention", "Churn"]
    )
    with overview:
        render_overview(start, end)
    with funnel_tab:
        render_funnel(start, end)
    with retention_tab:
        render_retention(start, end)
    with churn_tab:
        render_churn()


if __name__ == "__main__":
    main()
