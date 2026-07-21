"""Product Analytics Dashboard — Streamlit UI.

UI only: all metric logic lives in src/ (pure pandas, testable). This module
wires the cleaned clickstream into cached aggregations and renders three
sections — Overview (KPIs), Funnel, and Cohort Retention — each surfacing a
plain-English insight derived from the data, not just a chart.
"""

from __future__ import annotations

import os
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from src.churn import (
    FEATURES,
    at_risk_visitors,
    best_model_name,
    churn_insight,
    make_churn_dataset,
    predict_one,
    score_visitors,
    train_churn_models,
)
from src.data_load import load_events, sanity_report
from src.metrics import (
    FUNNEL_STAGES,
    cohort_retention,
    daily_active,
    funnel,
    kpis,
    top_items,
)

st.set_page_config(page_title="Product Analytics Dashboard", layout="wide")


# --- Cached data layer ----------------------------------------------------
# Cached metric functions key on the (start, end) date range — cheap to hash —
# and pull the full cached DataFrame internally, so the 2.7M-row frame is never
# re-hashed as a cache key on every rerun.


@st.cache_data(show_spinner="Loading clickstream…")
def get_data():
    # Bridge a Streamlit secret to the env var the UI-free loader reads, so the
    # app can fetch events.csv on Streamlit Cloud where data/ doesn't exist.
    try:
        url = st.secrets.get("EVENTS_URL")
    except Exception:
        url = None  # no secrets.toml present (e.g. local dev) — that's fine
    if url and not os.environ.get("EVENTS_URL"):
        os.environ["EVENTS_URL"] = url
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


# --- Cached aggregations, and how to invalidate them ------------------------
#
# Streamlit keys a @st.cache_data entry on the *wrapper's own source code*
# (`inspect.getsource`, comments included) plus the arguments actually passed —
# NOT on the src/ metric functions the wrapper calls, and NOT on default
# argument values. So when a metric function changes the SHAPE of its output —
# a new column, a rename — previously cached values stay live and the new UI
# code fails on them.
#
# That broke production once: funnel() gained `step_conversion_progressed`,
# get_funnel() kept serving cached 4-column frames, and render_funnel died with
# `KeyError: 'step_conversion_progressed'`.
#
# Each wrapper therefore carries a `cache-schema` comment. Bumping it edits the
# wrapper's source, which changes its cache key and discards stale entries.
# **Bump the relevant one whenever a src/ function's output shape changes.**


@st.cache_data(show_spinner="Computing KPIs…")
def get_kpis(start: date, end: date):
    # cache-schema: 1
    return kpis(_filter(start, end))


@st.cache_data(show_spinner="Building funnel…")
def get_funnel(start: date, end: date):
    # cache-schema: 2  (2: added visitors_progressed / step_conversion_progressed)
    return funnel(_filter(start, end))


@st.cache_data(show_spinner="Building cohorts…")
def get_cohorts(start: date, end: date):
    # cache-schema: 1
    return cohort_retention(_filter(start, end), freq="W")


@st.cache_data
def get_sanity(start: date, end: date):
    # cache-schema: 1
    return sanity_report(_filter(start, end))


@st.cache_data(show_spinner="Computing activity trend…")
def get_daily_active(start: date, end: date):
    # cache-schema: 1
    return daily_active(_filter(start, end))


@st.cache_data(show_spinner="Ranking items…")
def get_top_items(start: date, end: date, n: int = 20):
    # cache-schema: 1
    return top_items(_filter(start, end), n=n)


@st.cache_data(show_spinner="Building churn dataset…")
def get_churn_dataset():
    """Feature/label table from the full dataset — the obs/horizon windows are
    intrinsic to the churn definition and independent of the date filter."""
    return make_churn_dataset(get_data())


@st.cache_resource(show_spinner="Training churn model…")
def get_churn():
    """Fitted models + scores. cache_resource (not cache_data): sklearn models
    should be kept as live objects, not pickled on every access."""
    return train_churn_models(get_churn_dataset())


@st.cache_data(show_spinner="Scoring visitors…")
def get_scored():
    return score_visitors(get_churn(), get_churn_dataset())


# --- Insight helpers (plain English, computed from the data) --------------


def funnel_insight(f) -> str:
    """Name the biggest leak in the funnel from the step-conversion rates.

    Uses the progression rate, matching the per-step metrics rendered directly
    above it. Reading the drop off ``step_conversion`` instead would contradict
    them on screen — the metric would show 2.45% while the sentence claimed
    97.3% (= 1 - 2.69%) never continued.
    """
    steps = f.iloc[1:]  # rows after the top stage have a step_conversion
    worst = steps.loc[steps["step_conversion_progressed"].idxmin()]
    prev_stage = FUNNEL_STAGES[FUNNEL_STAGES.index(worst["stage"]) - 1]
    drop = 1 - worst["step_conversion_progressed"]
    overall = f.iloc[-1]["pct_of_top"]
    return (
        f"The biggest leak is **{prev_stage} → {worst['stage']}**: "
        f"**{drop:.1%}** of visitors who reach *{prev_stage}* never "
        f"continue to *{worst['stage']}*. End to end, only "
        f"**{overall:.2%}** of visitors who view an item go on to purchase."
    )


def progression_note(f) -> str | None:
    """Explain the gap between the stage-count and progression rates.

    Both steps can have a gap (in the full RetailRocket window, 8.8% of
    cart-adders have no recorded view and 9.8% of buyers no recorded cart), so
    rank by the gap as a *share* of the stage rather than by raw count — the
    absolute counts are not comparable across stages of very different size.

    Returns None when no stage has a meaningful gap (every visitor at each
    stage also reached the one before it), so we don't show a caveat about
    a discrepancy that isn't there.
    """
    steps = f.iloc[1:]
    gaps = (steps["visitors"] - steps["visitors_progressed"]) / steps["visitors"]
    if not (gaps > 0).any():
        return None

    row = steps.loc[gaps.idxmax()]
    stage = row["stage"]
    prev_stage = FUNNEL_STAGES[FUNNEL_STAGES.index(stage) - 1]
    skipped = int(row["visitors"] - row["visitors_progressed"])
    total = int(row["visitors"])
    return (
        f"**{skipped:,} of {total:,}** visitors who reached *{stage}* "
        f"({skipped / total:.1%}) have no recorded *{prev_stage}* event — a "
        f"tracking gap, or a path that skips that step. Counting all of them "
        f"gives a **{row['step_conversion']:.2%}** {prev_stage} → {stage} rate, "
        f"but they were never in the denominator. Measured as an actual "
        f"progression — visitors who did *both* — the step is "
        f"**{row['step_conversion_progressed']:.2%}**. Use the progression "
        f"figure when sizing an experiment on this step: it's the rate a change "
        f"there can actually move."
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

    da = get_daily_active(start, end)
    fig = go.Figure(
        go.Scatter(
            x=da.index,
            y=da.values,
            mode="lines",
            fill="tozeroy",
            line=dict(color="#2980b9", width=2),
            hovertemplate="%{x|%b %d, %Y}: %{y:,} visitors<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=280,
        title="Daily active visitors",
        yaxis_title="Distinct visitors",
    )
    st.plotly_chart(fig, use_container_width=True)

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

    steps = f.iloc[1:]
    cols = st.columns(len(steps))
    for col, (_, r) in zip(cols, steps.iterrows()):
        prev_stage = FUNNEL_STAGES[FUNNEL_STAGES.index(r["stage"]) - 1]
        col.metric(
            f"{prev_stage.capitalize()} → {r['stage'].capitalize()}",
            f"{r['step_conversion_progressed']:.2%}",
            help=(
                "Progression rate: visitors who reached this stage *and* the "
                "previous one, over previous-stage visitors. The stage-count "
                f"rate (all visitors at this stage / previous stage) is "
                f"{r['step_conversion']:.2%}."
            ),
        )

    note = progression_note(f)
    if note:
        st.warning(note)

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

    decay = c.mean()  # mean retention per week-offset across cohorts (skips NaN)
    fig2 = go.Figure(
        go.Scatter(
            x=decay.index,
            y=decay.values,
            mode="lines+markers",
            line=dict(color="#2980b9", width=2),
            hovertemplate="Week %{x}: %{y:.1%} retained<extra></extra>",
        )
    )
    fig2.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=280,
        title="Average retention decay (mean across cohorts)",
        xaxis_title="Weeks since first visit",
        yaxis=dict(title="Retained", tickformat=".0%"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.info(cohort_insight(c))
    st.caption(
        "Each row is the week a visitor first appeared; cells show the share "
        "active again N weeks later (any event = retained). The decay curve "
        "averages each column over the cohorts that could be observed that far."
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


def items_insight(items) -> str:
    """Call out the volume leader and the best-converting high-traffic item."""
    conv = items["view_to_purchase"].dropna()
    if conv.empty:
        return (
            "No item has enough views in this range for a reliable "
            "view→purchase conversion rate."
        )
    top_id, top = items.index[0], items.iloc[0]
    best_id = conv.idxmax()
    best = items.loc[best_id]
    return (
        f"Item **{top_id}** leads on volume with **{int(top['purchases'])}** "
        f"purchases from {int(top['views']):,} views, while item **{best_id}** "
        f"converts best — **{conv.max():.1%}** of its {int(best['views']):,} "
        "views end in a purchase."
    )


def render_items(start: date, end: date) -> None:
    items = get_top_items(start, end)
    st.subheader("Top Items")

    if items.empty:
        st.warning("No item activity in the selected date range.")
        return

    fig = go.Figure(
        go.Bar(
            x=[str(i) for i in items.index],
            y=items["purchases"],
            marker_color="#2980b9",
            hovertemplate="Item %{x}<br>%{y} purchases<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=320,
        title="Top items by purchases",
        xaxis=dict(title="Item ID", type="category"),
        yaxis_title="Purchases",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        items.style.format(
            {"view_to_purchase": "{:.2%}", "views": "{:,}"}, na_rep="—"
        ),
        use_container_width=True,
        height=340,
    )
    st.info(items_insight(items))
    st.caption(
        "Event counts per item; view→purchase conversion is only reported for "
        "items with ≥50 views so small samples can't top the ranking."
    )


def _prob_gauge(p: float) -> go.Figure:
    """Churn probability as a gauge: red when at risk, blue when likely back."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=p * 100,
            number={"suffix": "%", "font": {"size": 40}},
            title={"text": "Churn probability", "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100], "ticksuffix": "%"},
                "bar": {"color": "#c0392b" if p >= 0.5 else "#2980b9"},
                "threshold": {
                    "line": {"color": "gray", "width": 2},
                    "thickness": 0.75,
                    "value": 50,
                },
            },
        )
    )
    fig.update_layout(margin=dict(l=30, r=30, t=40, b=10), height=260)
    return fig


def _verdict(p: float) -> str:
    if p >= 0.9:
        return f"**{p:.0%}** likely to churn — almost certainly a one-time visitor."
    if p >= 0.5:
        return f"**{p:.0%}** likely to churn — at risk, worth a re-engagement nudge."
    return f"Only **{p:.0%}** churn risk — this visitor is likely to return."


def _render_lookup() -> None:
    scored = get_scored()
    samples = ", ".join(str(v) for v in scored.index[:5])
    vid = st.number_input(
        "Visitor ID (from the first-30-days window)",
        min_value=0,
        value=int(scored.index[0]),
        step=1,
    )
    st.caption(f"Try e.g.: {samples}")
    if vid not in scored.index:
        st.warning(
            "That visitor isn't in the observation window. Pick one of the "
            "sample IDs above."
        )
        return

    row = scored.loc[vid]
    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(_prob_gauge(row["churn_probability"]), use_container_width=True)
        st.markdown(_verdict(row["churn_probability"]))
    with right:
        feats = row[list(FEATURES)].rename("value").to_frame()
        feats.index = [f.replace("_", " ") for f in feats.index]
        st.dataframe(feats.style.format("{:.2f}"), use_container_width=True)


def _render_whatif(res: dict) -> None:
    st.caption(
        "Drag the sliders to describe a visitor's first-month behavior; the "
        "model predicts their churn risk live."
    )
    left, right = st.columns([1, 1])
    with left:
        num_events = st.slider("Events", 1, 60, 5)
        active_days = st.slider("Active days", 1, 30, 1)
        items = st.slider("Distinct items viewed", 1, 40, 3)
        carts = st.slider("Add-to-carts", 0, 10, 0)
        txns = st.slider("Purchases", 0, 5, 0)
        recency = st.slider("Days inactive at window end", 0, 30, 15)
        tenure = st.slider("Days between first & last visit", 0, 30, 0)

    features = {
        "num_events": num_events,
        "num_active_days": active_days,
        "num_distinct_items": items,
        "num_views": max(num_events - carts - txns, 0),
        "num_carts": carts,
        "num_transactions": txns,
        "recency_days": recency,
        "tenure_days": tenure,
        "events_per_active_day": num_events / active_days,
    }
    p = predict_one(res, features)
    with right:
        st.plotly_chart(_prob_gauge(p), use_container_width=True)
        st.markdown(_verdict(p))


def _render_at_risk() -> None:
    scored = get_scored()
    carted = scored[scored["num_carts"] > 0]
    carted_churn_share = (carted["churn_probability"] >= 0.5).mean()

    top_n = st.slider("List size", 25, 500, 100, step=25)
    risk = at_risk_visitors(scored, top_n=top_n)
    view = risk[
        [
            "churn_probability",
            "num_carts",
            "num_transactions",
            "num_events",
            "num_active_days",
            "recency_days",
        ]
    ].copy()
    st.dataframe(
        view.style.format(
            {"churn_probability": "{:.1%}", "recency_days": "{:.1f}"}
        ),
        use_container_width=True,
        height=340,
    )
    st.download_button(
        "Download as CSV",
        view.to_csv().encode("utf-8"),
        file_name="at_risk_visitors.csv",
        mime="text/csv",
    )
    st.info(
        f"**{carted_churn_share:.0%}** of the {len(carted):,} visitors who added "
        "to cart in their first month are predicted not to return — these are "
        "the highest-value re-engagement targets: they showed purchase intent, "
        "then went quiet."
    )


def render_churn() -> None:
    res = get_churn()
    st.subheader("Churn (Return-Prediction) Model")

    scores = res["scores"]
    best = best_model_name(res)
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

    st.divider()
    st.subheader("Predict")
    lookup, whatif, risk = st.tabs(
        ["🔍 Visitor lookup", "🎛 What-if", "⚠️ At-risk visitors"]
    )
    with lookup:
        _render_lookup()
    with whatif:
        _render_whatif(res)
    with risk:
        _render_at_risk()


def main() -> None:
    st.title("Product Analytics Dashboard")
    st.caption("RetailRocket clickstream — funnel, retention, and KPIs.")

    start, end = _date_range_picker()

    if get_sanity(start, end)["total_rows"] == 0:
        st.warning("No events in the selected date range. Widen the range.")
        return

    overview, funnel_tab, retention_tab, items_tab, churn_tab = st.tabs(
        ["Overview", "Funnel", "Retention", "Items", "Churn"]
    )
    with overview:
        render_overview(start, end)
    with funnel_tab:
        render_funnel(start, end)
    with retention_tab:
        render_retention(start, end)
    with items_tab:
        render_items(start, end)
    with churn_tab:
        render_churn()


if __name__ == "__main__":
    main()
