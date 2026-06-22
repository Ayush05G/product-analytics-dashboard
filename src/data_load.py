"""Load and clean the RetailRocket clickstream.

Pure data layer: no Streamlit imports. Produces a trustworthy, validated
DataFrame that the metric functions in ``metrics.py`` build on.
"""

from __future__ import annotations

import gzip
import os
import shutil
import urllib.request
from pathlib import Path

import pandas as pd

# RetailRocket only ever contains these three event types.
VALID_EVENTS: frozenset[str] = frozenset({"view", "addtocart", "transaction"})

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "events.csv"

# Optional URL to fetch events.csv when it isn't present locally (e.g. on
# Streamlit Community Cloud, where data/ is git-ignored). Read from the env so
# this module stays UI-free; app.py bridges st.secrets -> env. May point to a
# plain .csv or a gzipped .csv.gz.
ENV_DATA_URL = "EVENTS_URL"


def _download(url: str, dest: Path) -> Path:
    """Stream ``url`` to ``dest`` (decompressing if it ends in .gz).

    Writes to a temporary ``.part`` file first so an interrupted download can't
    leave a truncated events.csv that later loads look valid.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url) as resp, open(part, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    if url.lower().endswith(".gz"):
        with gzip.open(part, "rb") as gz, open(dest, "wb") as out:
            shutil.copyfileobj(gz, out)
        part.unlink()
    else:
        part.replace(dest)
    return dest


def resolve_data_path(path: str | Path = DEFAULT_PATH) -> Path:
    """Return a local path to events.csv, downloading it if necessary.

    Resolution order: (1) the local file if it exists; (2) download from the
    ``EVENTS_URL`` env var; (3) raise an actionable ``FileNotFoundError``.
    """
    path = Path(path)
    if path.exists():
        return path

    url = os.environ.get(ENV_DATA_URL)
    if url:
        return _download(url, path)

    raise FileNotFoundError(
        f"events.csv not found at {path} and {ENV_DATA_URL} is not set.\n"
        "Either place the RetailRocket events.csv in data/ (git-ignored), or "
        f"set {ENV_DATA_URL} to a direct download URL (.csv or .csv.gz). On "
        "Streamlit Community Cloud, add it under Settings -> Secrets as "
        f'`{ENV_DATA_URL} = "https://.../events.csv"`.'
    )


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
    path = resolve_data_path(path)

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
