"""Funnel + segment analysis backing the growth case study (case-study.md).

Computes the real figures the case study needs, prints them to the console, and
writes them to results/funnel_numbers.md. Analysis only: no Streamlit imports,
no dashboard code touched. Reuses src/data_load and src/metrics rather than
re-deriving the funnel.

Run from the repo root:  python scripts/funnel_analysis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.data_load import load_events, sanity_report  # noqa: E402
from src.metrics import funnel, kpis  # noqa: E402

RESULTS_PATH = REPO_ROOT / "results" / "funnel_numbers.md"

# Standard two-proportion sample-size constants: 95% two-sided confidence, 80%
# power. Hardcoded so the script needs no scipy (not in requirements.txt).
Z_ALPHA_2 = 1.959964
Z_BETA = 0.841621


# --------------------------------------------------------------------------
# Step 1 — visitor-level funnel
# --------------------------------------------------------------------------


def funnel_summary(df: pd.DataFrame) -> dict[str, float | int]:
    """Visitor-level funnel rates plus the absolute transaction base.

    Wraps ``metrics.funnel`` (which does the visitor-level counting) and adds
    the raw purchase counts the case study's impact section needs.
    """
    f = funnel(df).set_index("stage")
    viewers = int(f.loc["view", "visitors"])
    carters = int(f.loc["addtocart", "visitors"])
    buyers = int(f.loc["transaction", "visitors"])

    # Not every buyer passed through a recorded add-to-cart (tracking gaps, or
    # purchase paths that skip the cart). The naive buyers/carters ratio counts
    # those buyers in the numerator while they were never in the denominator,
    # which overstates the step. Use progression — buyers who *also* carted —
    # as the primary cart->purchase rate, and keep the naive one for contrast.
    view_set = set(df.loc[df["event"] == "view", "visitorid"])
    cart_set = set(df.loc[df["event"] == "addtocart", "visitorid"])
    buyer_set = set(df.loc[df["event"] == "transaction", "visitorid"])
    buyers_who_carted = len(buyer_set & cart_set)
    buyers_never_carted = len(buyer_set - cart_set)

    # The view -> addtocart step has the same gap: cart-adders with no recorded
    # view. Report it symmetrically so the case study can cite either step
    # without switching definitions mid-funnel.
    carters_who_viewed = len(cart_set & view_set)
    carters_never_viewed = len(cart_set - view_set)

    txn_rows = int((df["event"] == "transaction").sum())
    orders = (
        int(df.loc[df["event"] == "transaction", "transactionid"].nunique())
        if "transactionid" in df.columns
        else txn_rows
    )

    span_days = (df["timestamp"].max() - df["timestamp"].min()).days
    span_months = span_days / 30.4

    return {
        "viewers": viewers,
        "carters": carters,
        "buyers": buyers,
        "buyers_who_carted": buyers_who_carted,
        "buyers_never_carted": buyers_never_carted,
        "carters_who_viewed": carters_who_viewed,
        "carters_never_viewed": carters_never_viewed,
        "view_to_cart": carters_who_viewed / viewers,  # primary (progression)
        "view_to_cart_naive": carters / viewers,
        "cart_to_purchase": buyers_who_carted / carters,  # primary (progression)
        "cart_to_purchase_naive": buyers / carters,
        "view_to_purchase": buyers / viewers,
        "txn_rows": txn_rows,
        "orders": orders,
        "span_days": span_days,
        "orders_per_month": orders / span_months,
        "buyers_per_month": buyers / span_months,
    }


# --------------------------------------------------------------------------
# Step 2 — segment cuts of cart -> purchase
# --------------------------------------------------------------------------


def new_vs_returning(df: pd.DataFrame) -> pd.DataFrame:
    """Cart->purchase split by visitor status *at the moment of first cart*.

    ``returning`` = the visitor has >= 1 event on a calendar day strictly
    before their first add-to-cart day; ``new`` = their first-ever event falls
    on that same day.

    Status is judged at first-cart time on purpose. The simpler "active on 2+
    distinct days overall" definition has lookahead bias: purchasing itself
    generates later activity, so purchasers would be mechanically more likely
    to land in ``returning`` and the gap would be inflated.
    """
    day = df["timestamp"].dt.floor("D")
    work = pd.DataFrame(
        {"visitorid": df["visitorid"].to_numpy(), "day": day.to_numpy(),
         "event": df["event"].astype(str).to_numpy()}
    )

    first_any = work.groupby("visitorid")["day"].min()
    carts = work[work["event"] == "addtocart"]
    first_cart = carts.groupby("visitorid")["day"].min()

    status = pd.Series("new", index=first_cart.index, name="status")
    status[first_any.reindex(first_cart.index) < first_cart] = "returning"

    buyers = set(work.loc[work["event"] == "transaction", "visitorid"])
    converted = pd.Series(
        [v in buyers for v in first_cart.index], index=first_cart.index
    )

    out = pd.DataFrame({"status": status, "converted": converted})
    g = out.groupby("status")["converted"]
    res = pd.DataFrame({"cart_visitors": g.size(), "purchasers": g.sum()})
    res["cart_to_purchase"] = res["purchasers"] / res["cart_visitors"]
    return res.sort_values("cart_to_purchase")


def cart_size_segments(df: pd.DataFrame, window_days: int = 7) -> pd.DataFrame:
    """Cart->purchase split by single-item vs multi-item carts, per visitor-day.

    The data has no session or cart id, so a "cart" is approximated by the
    visitor-day: the unit of analysis is a (visitor, day) pair with >= 1
    add-to-cart, and ``multi`` means >= 2 distinct itemids added that day.
    Bucketing over the whole ~4.5-month window instead would wrongly label a
    visitor who added one item in March and one in June as a multi-item cart.

    Converted (primary) = the visitor has a transaction on that same day. Also
    reports a ``conv_window`` variant allowing the purchase within
    ``window_days`` after, as a robustness check.
    """
    day = df["timestamp"].dt.floor("D")
    work = pd.DataFrame(
        {"visitorid": df["visitorid"].to_numpy(), "day": day.to_numpy(),
         "itemid": df["itemid"].to_numpy(), "event": df["event"].astype(str).to_numpy()}
    )

    carts = work[work["event"] == "addtocart"]
    cart_days = (
        carts.groupby(["visitorid", "day"])["itemid"].nunique().reset_index(name="items")
    )
    cart_days["segment"] = cart_days["items"].gt(1).map(
        {False: "single-item", True: "multi-item"}
    )

    txns = work[work["event"] == "transaction"][["visitorid", "day"]].drop_duplicates()

    # Same-day conversion: inner-join cart-days against transaction-days.
    same_day = cart_days.merge(
        txns.assign(bought=True), on=["visitorid", "day"], how="left"
    )
    cart_days["converted"] = same_day["bought"].fillna(False).to_numpy()

    # Windowed variant: any transaction in [cart_day, cart_day + window_days].
    pairs = cart_days[["visitorid", "day"]].merge(txns, on="visitorid", how="left",
                                                  suffixes=("", "_txn"))
    delta = (pairs["day_txn"] - pairs["day"]).dt.days
    pairs["in_window"] = delta.between(0, window_days)
    win = pairs.groupby(["visitorid", "day"])["in_window"].any()
    cart_days["converted_window"] = (
        win.reindex(pd.MultiIndex.from_frame(cart_days[["visitorid", "day"]]))
        .fillna(False)
        .to_numpy()
    )

    g = cart_days.groupby("segment")
    res = pd.DataFrame(
        {
            "cart_days": g.size(),
            "purchases": g["converted"].sum(),
            "cart_to_purchase": g["converted"].mean(),
            "conv_window": g["converted_window"].mean(),
        }
    )
    return res.sort_values("cart_to_purchase")


def crossed_segments(df: pd.DataFrame) -> pd.DataFrame:
    """Cart->purchase crossed by visitor status x cart size, at visitor-day grain.

    The case study argues the actionable pocket lives in a *combination* of
    segments, not the average, so report the 2x2 as well as the marginals.
    """
    day = df["timestamp"].dt.floor("D")
    work = pd.DataFrame(
        {"visitorid": df["visitorid"].to_numpy(), "day": day.to_numpy(),
         "itemid": df["itemid"].to_numpy(), "event": df["event"].astype(str).to_numpy()}
    )

    first_any = work.groupby("visitorid")["day"].min()
    carts = work[work["event"] == "addtocart"]
    cart_days = (
        carts.groupby(["visitorid", "day"])["itemid"].nunique().reset_index(name="items")
    )
    cart_days["size_seg"] = cart_days["items"].gt(1).map(
        {False: "single-item", True: "multi-item"}
    )
    # Status judged per cart-day: any activity before *this* cart day.
    cart_days["status"] = (
        first_any.reindex(cart_days["visitorid"]).to_numpy() < cart_days["day"].to_numpy()
    )
    cart_days["status"] = cart_days["status"].map({False: "new", True: "returning"})

    txns = work[work["event"] == "transaction"][["visitorid", "day"]].drop_duplicates()
    merged = cart_days.merge(txns.assign(bought=True), on=["visitorid", "day"], how="left")
    cart_days["converted"] = merged["bought"].fillna(False).to_numpy()

    g = cart_days.groupby(["status", "size_seg"])
    res = pd.DataFrame(
        {"cart_days": g.size(), "purchases": g["converted"].sum(),
         "cart_to_purchase": g["converted"].mean()}
    )
    return res.sort_values("cart_to_purchase")


# --------------------------------------------------------------------------
# Step 5 support — sample size for the experiment MDE
# --------------------------------------------------------------------------


def sample_size_per_arm(baseline: float, relative_lift: float) -> int:
    """Visitors per arm to detect ``relative_lift`` on ``baseline``.

    Two-proportion z-test, 95% two-sided confidence, 80% power. Standard
    pooled-variance approximation.
    """
    p1 = baseline
    p2 = baseline * (1 + relative_lift)
    p_bar = (p1 + p2) / 2
    numerator = (
        Z_ALPHA_2 * (2 * p_bar * (1 - p_bar)) ** 0.5
        + Z_BETA * (p1 * (1 - p1) + p2 * (1 - p2)) ** 0.5
    ) ** 2
    return int(-(-numerator / (p2 - p1) ** 2 // 1))  # ceil


def weekly_cart_adders(df: pd.DataFrame) -> float:
    """Mean distinct visitors adding to cart per ISO week — the traffic an
    experiment on the cart step can actually draw on."""
    carts = df[df["event"] == "addtocart"]
    week = carts["timestamp"].dt.tz_localize(None).dt.to_period("W")
    return float(carts.groupby(week)["visitorid"].nunique().mean())


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{x:.2%}"


def build_report(df: pd.DataFrame) -> str:
    """Assemble the full markdown report (also what gets printed)."""
    rep = sanity_report(df)
    fs = funnel_summary(df)
    k = kpis(df)
    nvr = new_vs_returning(df)
    cs = cart_size_segments(df)
    cross = crossed_segments(df)

    baseline = fs["cart_to_purchase"]
    weekly = weekly_cart_adders(df)
    n5 = sample_size_per_arm(baseline, 0.05)
    n10 = sample_size_per_arm(baseline, 0.10)
    n20 = sample_size_per_arm(baseline, 0.20)

    worst_status = nvr.index[0]
    worst_size = cs.index[0]
    worst_cross = cross.index[0]

    lines: list[str] = []
    add = lines.append

    add("# Funnel numbers — source figures for case-study.md")
    add("")
    add("Generated by `scripts/funnel_analysis.py` from the real RetailRocket")
    add("`data/events.csv`. Every figure here is computed, none illustrative.")
    add("")
    add("## Sanity check (verify before trusting anything below)")
    add("")
    add(f"- Total rows: **{rep['total_rows']:,}**")
    add(f"- Unique visitors: **{rep['unique_visitors']:,}**")
    add("- Event-type counts:")
    for event, count in sorted(rep["event_counts"].items(), key=lambda kv: -kv[1]):
        add(f"  - `{event}`: {count:,} ({count / rep['total_rows']:.2%})")
    add(f"- Date range: {rep['date_min']:%Y-%m-%d} → {rep['date_max']:%Y-%m-%d} "
        f"({fs['span_days']} days, ~{fs['span_days'] / 30.4:.1f} months)")
    add("")
    add("## 1. Visitor-level funnel")
    add("")
    add("Counts distinct *people* who reached each stage, not raw events.")
    add("")
    add("| Stage | Visitors | Step conv. (stage-count) | Step conv. (progression) "
        "| Cumulative |")
    add("|---|---:|---:|---:|---:|")
    add(f"| Viewed a product | {fs['viewers']:,} | — | — | 100% |")
    add(f"| Added to cart | {fs['carters']:,} | {_pct(fs['view_to_cart_naive'])} "
        f"| **{_pct(fs['view_to_cart'])}** | {_pct(fs['view_to_cart_naive'])} |")
    add(f"| Purchased | {fs['buyers']:,} | {_pct(fs['cart_to_purchase_naive'])} "
        f"| **{_pct(fs['cart_to_purchase'])}** | {_pct(fs['view_to_purchase'])} |")
    add("")
    add("**Step-conversion caveat — it applies to BOTH steps.** Not everyone at "
        "a stage passed through the stage recorded before it:")
    add("")
    add(f"- {fs['buyers_never_carted']:,} of {fs['buyers']:,} buyers "
        f"({fs['buyers_never_carted'] / fs['buyers']:.1%}) have no `addtocart` "
        "event at all.")
    add(f"- {fs['carters_never_viewed']:,} of {fs['carters']:,} cart-adders "
        f"({fs['carters_never_viewed'] / fs['carters']:.1%}) have no `view` "
        "event at all.")
    add("")
    add("Dividing all of a stage by the previous stage counts those people in "
        "the numerator while they were never in the denominator, inflating "
        f"cart→purchase to **{_pct(fs['cart_to_purchase_naive'])}** and "
        f"view→cart to **{_pct(fs['view_to_cart_naive'])}**. The progression "
        "column counts only visitors who reached both the stage and the one "
        f"before it — {fs['buyers_who_carted']:,} buyers who also carted "
        f"(**{_pct(fs['cart_to_purchase'])}**) and {fs['carters_who_viewed']:,} "
        f"cart-adders who also viewed (**{_pct(fs['view_to_cart'])}**). The case "
        "study uses the progression column throughout. "
        "(`metrics.funnel()` reports both: `step_conversion` for the "
        "stage-count view and `step_conversion_progressed` for this one. The "
        "naive figure is not wrong, it just answers a different question.)")
    add("")
    add(f"- Visitors with no recorded `view` event: "
        f"{rep['unique_visitors'] - fs['viewers']:,} "
        f"({(rep['unique_visitors'] - fs['viewers']) / rep['unique_visitors']:.2%}) "
        "— why `view→purchase` (viewer-denominated) and "
        "`kpis.conversion_rate` (all-visitor-denominated) differ slightly.")
    add(f"- Transaction event rows over the period: **{fs['txn_rows']:,}**")
    add(f"- Distinct orders (`transactionid`): **{fs['orders']:,}**")
    add(f"- Orders per month: **{fs['orders_per_month']:,.0f}**")
    add(f"- Distinct purchasers per month: **{fs['buyers_per_month']:,.0f}**")
    add("")
    add("## 2. Segment cuts of cart→purchase")
    add("")
    add("### 2a. New vs returning (visitor grain)")
    add("")
    add("`returning` = had activity on a calendar day strictly *before* their first")
    add("add-to-cart day; `new` = first-ever event on that same day. Judged at the")
    add("moment of intent to avoid lookahead bias (purchasing itself generates later")
    add("activity, which would inflate a whole-window 'returning' definition).")
    add("")
    add("| Segment | Cart visitors | Purchasers | Cart→purchase |")
    add("|---|---:|---:|---:|")
    for seg, r in nvr.iterrows():
        add(f"| {seg} | {int(r['cart_visitors']):,} | {int(r['purchasers']):,} | "
            f"{_pct(r['cart_to_purchase'])} |")
    add("")
    add("### 2b. Single-item vs multi-item carts (visitor-day grain)")
    add("")
    add("No session/cart id exists in the data, so a cart is approximated by the")
    add("visitor-day. `multi-item` = ≥2 distinct itemids added that day. Primary")
    add("conversion is same-day; `conv (7d)` allows the purchase within 7 days as a")
    add("robustness check.")
    add("")
    add("| Segment | Cart-days | Purchases | Cart→purchase (same-day) | conv (7d) |")
    add("|---|---:|---:|---:|---:|")
    for seg, r in cs.iterrows():
        add(f"| {seg} | {int(r['cart_days']):,} | {int(r['purchases']):,} | "
            f"{_pct(r['cart_to_purchase'])} | {_pct(r['conv_window'])} |")
    add("")
    add("### 2c. Crossed: status × cart size (visitor-day grain, same-day)")
    add("")
    add("| Status | Cart size | Cart-days | Purchases | Cart→purchase |")
    add("|---|---|---:|---:|---:|")
    for (status, size_seg), r in cross.iterrows():
        add(f"| {status} | {size_seg} | {int(r['cart_days']):,} | "
            f"{int(r['purchases']):,} | {_pct(r['cart_to_purchase'])} |")
    add("")
    add("### Worst-converting segments")
    add("")
    add(f"- By status: **{worst_status}** at "
        f"{_pct(nvr.loc[worst_status, 'cart_to_purchase'])}")
    add(f"- By cart size: **{worst_size}** at "
        f"{_pct(cs.loc[worst_size, 'cart_to_purchase'])}")
    add(f"- Crossed: **{worst_cross[0]} / {worst_cross[1]}** at "
        f"{_pct(cross.loc[worst_cross, 'cart_to_purchase'])} "
        f"({int(cross.loc[worst_cross, 'cart_days']):,} cart-days)")
    add("")
    add("## 3. Experiment sizing (for the MDE in section 4 of the case study)")
    add("")
    add(f"Baseline cart→purchase (visitor-level): **{_pct(baseline)}**")
    add(f"Mean distinct cart-adders per week: **{weekly:,.0f}**")
    add("")
    add("Two-proportion z-test, 95% two-sided confidence, 80% power:")
    add("")
    add("| Relative lift (MDE) | Visitors per arm | Total (2 arms) | Weeks at observed traffic |")
    add("|---|---:|---:|---:|")
    for lift, n in ((0.05, n5), (0.10, n10), (0.20, n20)):
        total = 2 * n
        add(f"| +{lift:.0%} | {n:,} | {total:,} | {total / weekly:,.1f} |")
    add("")
    add("## 4. Cross-checks")
    add("")
    add(f"- `metrics.kpis()['conversion_rate']` = {_pct(k['conversion_rate'])} "
        f"= buyers / all visitors; funnel view→purchase = "
        f"{_pct(fs['view_to_purchase'])} = buyers / viewers. The gap is exactly "
        "the no-view visitors noted above — two independent paths, reconciled.")
    add(f"- Funnel stages are monotonic: {fs['viewers']:,} ≥ {fs['carters']:,} "
        f"≥ {fs['buyers']:,}")
    add(f"- All stages ≤ total visitors ({rep['unique_visitors']:,})")
    add("")
    return "\n".join(lines)


def _verify(df: pd.DataFrame) -> None:
    """Assertions that must hold before any of these numbers are quoted."""
    fs = funnel_summary(df)
    k = kpis(df)
    rep = sanity_report(df)

    assert fs["viewers"] >= fs["carters"] >= fs["buyers"], "funnel not monotonic"
    assert fs["viewers"] <= rep["unique_visitors"], "stage exceeds total visitors"

    # kpis() divides converters by ALL visitors; the funnel divides by viewers.
    # They differ only by the visitors with no recorded view event, so check
    # that identity rather than asserting the two rates are equal.
    assert abs(fs["buyers"] / rep["unique_visitors"] - k["conversion_rate"]) < 1e-9, (
        "kpis conversion_rate is not buyers/total_visitors"
    )
    assert fs["view_to_purchase"] >= k["conversion_rate"], (
        "viewer-denominated rate must be >= all-visitor rate"
    )

    for rate in ("view_to_cart", "cart_to_purchase", "cart_to_purchase_naive",
                 "view_to_purchase"):
        assert 0 <= fs[rate] <= 1, f"{rate} out of range"

    assert fs["buyers_who_carted"] + fs["buyers_never_carted"] == fs["buyers"], (
        "carted/never-carted buyers do not sum to total buyers"
    )
    assert fs["cart_to_purchase"] <= fs["cart_to_purchase_naive"], (
        "progression rate cannot exceed the naive rate"
    )

    # This script derives progression independently (set intersection above);
    # metrics.funnel() now derives it too. Keep both and cross-check them —
    # if they ever disagree, one of the two is wrong and the case study's
    # headline number is in doubt.
    f = funnel(df).set_index("stage")
    assert int(f.loc["transaction", "visitors_progressed"]) == fs["buyers_who_carted"], (
        "metrics.funnel() progression count disagrees with this script's"
    )
    assert abs(
        f.loc["transaction", "step_conversion_progressed"] - fs["cart_to_purchase"]
    ) < 1e-12, "metrics.funnel() progression rate disagrees with this script's"
    assert int(f.loc["addtocart", "visitors_progressed"]) == fs["carters_who_viewed"], (
        "metrics.funnel() view-step progression count disagrees with this script's"
    )
    assert abs(
        f.loc["addtocart", "step_conversion_progressed"] - fs["view_to_cart"]
    ) < 1e-12, "metrics.funnel() view-step progression rate disagrees with this script's"

    # Both steps: the two populations must partition the stage exactly.
    assert fs["carters_who_viewed"] + fs["carters_never_viewed"] == fs["carters"], (
        "viewed/never-viewed cart-adders do not sum to the cart stage"
    )
    assert fs["view_to_cart"] <= fs["view_to_cart_naive"], (
        "view-step progression rate cannot exceed the naive rate"
    )

    nvr = new_vs_returning(df)
    assert int(nvr["cart_visitors"].sum()) == fs["carters"], (
        "new/returning segments do not sum to the cart stage"
    )
    assert int(nvr["purchasers"].sum()) == fs["buyers_who_carted"], (
        "segment purchasers do not sum to buyers who carted"
    )
    assert nvr["cart_to_purchase"].between(0, 1).all(), "segment rate out of range"

    cs = cart_size_segments(df)
    assert cs["cart_to_purchase"].between(0, 1).all(), "cart-size rate out of range"
    assert (cs["conv_window"] >= cs["cart_to_purchase"]).all(), (
        "7-day conversion cannot be below same-day"
    )

    cross = crossed_segments(df)
    assert int(cross["cart_days"].sum()) == int(cs["cart_days"].sum()), (
        "crossed segments do not sum to the cart-day total"
    )

    thin = cross[cross["cart_days"] < 100]
    if not thin.empty:
        print(f"WARNING: thin segment cells (<100 cart-days):\n{thin}\n")


def main() -> None:
    # The report contains arrows/box-drawing; the default Windows console
    # codepage (cp1252) can't encode them. Force UTF-8 on stdout.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    df = load_events()
    _verify(df)
    report = build_report(df)
    print(report)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(report, encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
