"""Product Analytics Dashboard — Streamlit UI.

UI only: all metric logic lives in src/ (pure pandas, testable). This module
wires the cleaned clickstream into cached aggregations and renders three
sections — Overview (KPIs), Funnel, and Cohort Retention — each surfacing a
plain-English insight derived from the data, not just a chart.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.data_load import load_events, sanity_report
from src.metrics import FUNNEL_STAGES, cohort_retention, funnel, kpis

st.set_page_config(page_title="Product Analytics Dashboard", layout="wide")


# --- Cached data layer ----------------------------------------------------
# Each cached function takes no args and pulls the cached DataFrame internally,
# so the 2.7M-row frame is never re-hashed as a cache key on every rerun.


@st.cache_data(show_spinner="Loading clickstream…")
def get_data():
    return load_events()


@st.cache_data(show_spinner="Computing KPIs…")
def get_kpis():
    return kpis(get_data())


@st.cache_data(show_spinner="Building funnel…")
def get_funnel():
    return funnel(get_data())


@st.cache_data(show_spinner="Building cohorts…")
def get_cohorts():
    return cohort_retention(get_data(), freq="W")


@st.cache_data
def get_sanity():
    return sanity_report(get_data())


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


def render_overview() -> None:
    k = get_kpis()
    s = get_sanity()
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


def render_funnel() -> None:
    f = get_funnel()
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


def render_retention() -> None:
    c = get_cohorts()
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


def main() -> None:
    st.title("Product Analytics Dashboard")
    st.caption("RetailRocket clickstream — funnel, retention, and KPIs.")

    overview, funnel_tab, retention_tab = st.tabs(
        ["Overview", "Funnel", "Retention"]
    )
    with overview:
        render_overview()
    with funnel_tab:
        render_funnel()
    with retention_tab:
        render_retention()


if __name__ == "__main__":
    main()
