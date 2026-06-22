"""Churn (return-prediction) model over the clickstream.

Behavioral churn definition (no accounts exist in RetailRocket):

    Observation window : the first ``obs_days`` of the dataset.
    Horizon window     : the following ``horizon_days``.
    Population         : visitors with >= 1 event in the observation window.
    Label              : ``churned = 1`` if the visitor has NO event in the
                         horizon window, else 0 (they returned).

All features are computed from the observation window only, so the horizon
(the thing we predict) never leaks into the inputs. Pure modeling logic — no
Streamlit imports — mirroring metrics.py so it stays testable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Behavioral features built from the observation window.
FEATURES: tuple[str, ...] = (
    "num_events",
    "num_active_days",
    "num_distinct_items",
    "num_views",
    "num_carts",
    "num_transactions",
    "recency_days",  # days from last obs event to end of obs window (lower = more recent)
    "tenure_days",  # span from first to last obs event
    "events_per_active_day",
)


def make_churn_dataset(
    df: pd.DataFrame, obs_days: int = 30, horizon_days: int = 30
) -> pd.DataFrame:
    """Build a one-row-per-visitor feature/label table.

    Returns a DataFrame indexed by ``visitorid`` with the ``FEATURES`` columns
    plus a ``churned`` label (1 = did not return in the horizon). Raises
    ``ValueError`` if the dataset is too short to contain both windows or the
    observation window has no events.
    """
    ref = df["timestamp"].min()
    obs_end = ref + pd.Timedelta(days=obs_days)
    hor_end = obs_end + pd.Timedelta(days=horizon_days)
    if df["timestamp"].max() < hor_end:
        raise ValueError(
            f"dataset spans {(df['timestamp'].max() - ref).days} days; need at "
            f"least {obs_days + horizon_days} for obs+horizon windows."
        )

    ts = df["timestamp"]
    obs = df[(ts >= ref) & (ts < obs_end)]
    hor = df[(ts >= obs_end) & (ts < hor_end)]
    if obs.empty:
        raise ValueError("no events in the observation window.")

    returned = set(hor["visitorid"].unique())

    obs = obs.assign(
        day=obs["timestamp"].dt.floor("D"),
        is_view=(obs["event"] == "view"),
        is_cart=(obs["event"] == "addtocart"),
        is_txn=(obs["event"] == "transaction"),
    )
    g = obs.groupby("visitorid")
    feat = g.agg(
        num_events=("event", "size"),
        num_active_days=("day", "nunique"),
        num_distinct_items=("itemid", "nunique"),
        num_views=("is_view", "sum"),
        num_carts=("is_cart", "sum"),
        num_transactions=("is_txn", "sum"),
        last_ts=("timestamp", "max"),
        first_ts=("timestamp", "min"),
    )

    feat["recency_days"] = (obs_end - feat["last_ts"]).dt.total_seconds() / 86400
    feat["tenure_days"] = (
        feat["last_ts"] - feat["first_ts"]
    ).dt.total_seconds() / 86400
    feat["events_per_active_day"] = feat["num_events"] / feat["num_active_days"]
    feat["churned"] = (~feat.index.isin(returned)).astype(int)

    return feat.drop(columns=["last_ts", "first_ts"])


def train_churn_models(
    dataset: pd.DataFrame, test_size: float = 0.25, seed: int = 42
) -> dict:
    """Train a logistic-regression baseline and gradient-boosted trees.

    Returns a dict with each model, its held-out ROC-AUC / PR-AUC, the test
    split, the base churn rate, and the standardized logistic coefficients
    (for the interpretable insight).
    """
    X = dataset[list(FEATURES)].to_numpy(dtype=float)
    y = dataset["churned"].to_numpy()

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=seed
    )

    logreg = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    ).fit(X_tr, y_tr)
    gbm = HistGradientBoostingClassifier(random_state=seed).fit(X_tr, y_tr)

    models = {"logreg": logreg, "gbm": gbm}
    scores: dict[str, dict[str, float]] = {}
    for name, model in models.items():
        proba = model.predict_proba(X_te)[:, 1]
        scores[name] = {
            "roc_auc": float(roc_auc_score(y_te, proba)),
            "pr_auc": float(average_precision_score(y_te, proba)),
        }

    # Standardized logistic coefficients: directly comparable across features
    # because StandardScaler put every input on a unit-variance scale.
    coefs = dict(
        zip(FEATURES, logreg.named_steps["logisticregression"].coef_[0])
    )

    return {
        "models": models,
        "scores": scores,
        "coefs": coefs,
        "base_rate": float(y.mean()),
        "n_visitors": int(len(y)),
        "X_test": X_te,
        "y_test": y_te,
    }


def churn_insight(result: dict) -> str:
    """Plain-English summary from the standardized logistic coefficients."""
    coefs = result["coefs"]
    top_churn = max(coefs, key=coefs.get)  # most positive -> pushes toward churn
    top_retain = min(coefs, key=coefs.get)  # most negative -> pushes toward return
    best_model = max(result["scores"], key=lambda m: result["scores"][m]["roc_auc"])
    best_auc = result["scores"][best_model]["roc_auc"]
    return (
        f"**{result['base_rate']:.0%}** of first-window visitors never return in "
        f"the next 30 days. The model separates returners from churners with "
        f"**ROC-AUC {best_auc:.3f}** ({best_model}). The strongest churn signal is "
        f"high **{top_churn.replace('_', ' ')}**, while high "
        f"**{top_retain.replace('_', ' ')}** most predicts a return — i.e. early "
        f"breadth and recency of engagement is what retains visitors."
    )


def _print_report(df: pd.DataFrame) -> None:
    print("Building churn dataset (obs=30d, horizon=30d)…")
    data = make_churn_dataset(df)
    print(f"  visitors in observation window : {len(data):,}")
    print(f"  churn (no return) base rate    : {data['churned'].mean():.2%}")

    print("\nTraining models…")
    res = train_churn_models(data)
    print(f"  n visitors (modeled) : {res['n_visitors']:,}")
    print("  held-out performance :")
    for name, s in res["scores"].items():
        print(f"    {name:<8} ROC-AUC {s['roc_auc']:.3f}  PR-AUC {s['pr_auc']:.3f}")

    print("\n  standardized logistic coefficients (sign = churn direction):")
    for feat, c in sorted(res["coefs"].items(), key=lambda kv: -abs(kv[1])):
        arrow = "churn↑" if c > 0 else "return↑"
        print(f"    {feat:<22} {c:+.3f}  ({arrow})")

    print("\nINSIGHT:", churn_insight(res))

    # Internal-consistency checks.
    assert 0 < res["base_rate"] < 1, "degenerate label distribution"
    for s in res["scores"].values():
        assert 0.5 <= s["roc_auc"] <= 1.0, "AUC below chance — pipeline bug"
    assert not np.isnan(list(res["coefs"].values())).any()
    print("\nAll internal-consistency checks passed.")


if __name__ == "__main__":
    from data_load import load_events

    _print_report(load_events())
