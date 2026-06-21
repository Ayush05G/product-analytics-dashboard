"""Load and clean the RetailRocket clickstream.

Pure data layer: no Streamlit imports. Produces a trustworthy, validated
DataFrame that the metric functions in ``metrics.py`` build on.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# RetailRocket only ever contains these three event types.
VALID_EVENTS: frozenset[str] = frozenset({"view", "addtocart", "transaction"})

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "events.csv"


def _parse_timestamp(ts: pd.Series) -> pd.Series:
    """Convert the epoch ``timestamp`` column to tz-aware UTC datetimes.

    RetailRocket stores Unix time in *milliseconds* (13-digit integers). We
    auto-detect the unit by magnitude so a seconds-based export can't be
    silently mis-parsed into the year 1970 (or 48,000).
    """
    ts = pd.to_numeric(ts, errors="coerce")
    if ts.isna().any():
        raise ValueError("timestamp column contains non-numeric values")

    # ~1e12 = ms since 1970; ~1e9 = s since 1970. Pick by order of magnitude.
    median = ts.median()
    if median > 1e14:
        unit = "us"
    elif median > 1e11:
        unit = "ms"
    elif median > 1e8:
        unit = "s"
    else:
        raise ValueError(f"unrecognized timestamp magnitude (median={median})")

    return pd.to_datetime(ts, unit=unit, utc=True)


def load_events(path: str | Path = DEFAULT_PATH) -> pd.DataFrame:
    """Load ``events.csv`` and return a cleaned, validated DataFrame.

    Steps: read CSV -> parse timestamp -> drop exact duplicates ->
    validate event types -> coerce dtypes -> sort chronologically.

    Returns columns: ``timestamp`` (datetime64[ns, UTC]), ``visitorid`` (int),
    ``event`` (category), ``itemid`` (int), and ``transactionid`` (nullable
    Int64; only populated for transaction rows) when present in the source.

    Raises ``FileNotFoundError`` if the data file is missing and ``ValueError``
    on unexpected event types or unparseable timestamps.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"events.csv not found at {path}. Place the RetailRocket dataset "
            "in data/ (it is git-ignored)."
        )

    df = pd.read_csv(path)

    expected = {"timestamp", "visitorid", "event", "itemid"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"events.csv missing expected columns: {sorted(missing)}")

    df["timestamp"] = _parse_timestamp(df["timestamp"])

    # Drop fully-duplicate rows (same visitor, same event, same item, same ms).
    df = df.drop_duplicates()

    # Validate event types before we trust any aggregate built on them.
    bad = set(df["event"].unique()) - VALID_EVENTS
    if bad:
        raise ValueError(f"unexpected event types: {sorted(bad)}")

    df["visitorid"] = df["visitorid"].astype("int64")
    df["itemid"] = df["itemid"].astype("int64")
    df["event"] = df["event"].astype("category")
    if "transactionid" in df.columns:
        # Only set on transaction rows; keep it nullable.
        df["transactionid"] = df["transactionid"].astype("Int64")

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def sanity_report(df: pd.DataFrame) -> dict[str, object]:
    """Compute the headline totals used to eyeball that the load is correct."""
    return {
        "total_rows": len(df),
        "unique_visitors": df["visitorid"].nunique(),
        "event_counts": df["event"].value_counts().to_dict(),
        "date_min": df["timestamp"].min(),
        "date_max": df["timestamp"].max(),
    }


def _print_sanity_report(df: pd.DataFrame) -> None:
    rep = sanity_report(df)
    span_days = (rep["date_max"] - rep["date_min"]).days
    print("=== events.csv sanity check ===")
    print(f"Total rows        : {rep['total_rows']:,}")
    print(f"Unique visitors   : {rep['unique_visitors']:,}")
    print("Event-type counts :")
    for event, count in sorted(rep["event_counts"].items(), key=lambda kv: -kv[1]):
        share = count / rep["total_rows"]
        print(f"    {event:<12} {count:>10,}  ({share:6.2%})")
    print(f"Date range        : {rep['date_min']}  ->  {rep['date_max']}")
    print(f"Span              : {span_days} days (~{span_days / 30.4:.1f} months)")


if __name__ == "__main__":
    _print_sanity_report(load_events())
