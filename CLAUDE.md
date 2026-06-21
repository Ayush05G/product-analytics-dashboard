# Product Analytics Dashboard

## What this is
A dashboard that turns a real e-commerce clickstream into product metrics:
conversion funnels, cohort retention, and KPI overview — each surfacing a
plain-English insight, not just a chart. Built as a reusable analytics engine:
the same funnel/cohort logic generalizes to any event stream (e.g. a fintech app).

## Dataset
RetailRocket `events.csv` (real data): columns timestamp, visitorid, event
(view | addtocart | transaction), itemid. ~2.7M events over ~4.5 months.
This is REAL data — never replace it with synthetic data. Raw data lives in
`data/` and is git-ignored (it's large); never commit it.

## Tech stack
- Python 3.11+, pandas (wrangling), Plotly (charts), Streamlit (app)
- Deploy: Streamlit Community Cloud
- scikit-learn only if/when the stretch churn model is built

## Structure
- `data/` — raw + processed data (git-ignored)
- `src/metrics.py` — pure functions: funnel(), cohort_retention(), kpis().
  No Streamlit imports here — keep metric logic UI-free and testable.
- `src/data_load.py` — load + clean events
- `app.py` — Streamlit UI only; imports from src/
- `notebooks/` — optional EDA scratch

## Key constraints
- Correctness first: metric numbers must be right. Sanity-check against known
  dataset totals (row count, unique visitors, event-type breakdown) before
  trusting any aggregate.
- Cache expensive aggregations with @st.cache_data — never recompute on every
  interaction.
- Every dashboard section must display at least one plain-English insight
  derived from the data, not just a visualization.
- Keep funnel/cohort/KPI logic as pure functions separate from the UI.
- Data quality: handle missing/duplicate/out-of-range rows explicitly during
  load (don't silently drop them — log what was removed and why). Timestamps
  are Unix epoch milliseconds; convert and validate the resulting date range.

## Conventions
- Type hints on functions. Small, single-purpose functions.
- Commit at logical checkpoints with clear messages.

## Workflow notes
- If a feature's requirements are unclear, ask me clarifying questions first.
- When I correct a mistake, add a rule to this file so it doesn't repeat.
