"""Tests for the data layer: timestamp parsing, cleaning, validation, and the
data-source resolution logic."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_load import (
    _parse_timestamp,
    load_events,
    resolve_data_path,
    sanity_report,
)

HEADER = "timestamp,visitorid,event,itemid,transactionid\n"


def _write_csv(path, rows: list[str]) -> None:
    path.write_text(HEADER + "\n".join(rows) + "\n")


def test_parse_timestamp_milliseconds():
    out = _parse_timestamp(pd.Series([1433221332117]))  # 13-digit ms
    assert out.dt.year.iloc[0] == 2015


def test_parse_timestamp_seconds():
    out = _parse_timestamp(pd.Series([1433221332]))  # 10-digit s
    assert out.dt.year.iloc[0] == 2015


def test_parse_timestamp_rejects_tiny_magnitude():
    with pytest.raises(ValueError):
        _parse_timestamp(pd.Series([12, 34]))


def test_load_drops_exact_duplicates(tmp_path):
    csv = tmp_path / "events.csv"
    _write_csv(
        csv,
        [
            "1433221332117,1,view,100,",
            "1433221332117,1,view,100,",  # exact duplicate -> dropped
            "1433221400000,2,view,200,",
        ],
    )
    assert len(load_events(csv)) == 2


def test_load_rejects_unknown_event_type(tmp_path):
    csv = tmp_path / "events.csv"
    _write_csv(csv, ["1433221332117,1,click,100,"])
    with pytest.raises(ValueError):
        load_events(csv)


def test_load_dtypes_and_sorted(tmp_path):
    csv = tmp_path / "events.csv"
    _write_csv(
        csv,
        [
            "1433221400000,2,view,200,",  # later
            "1433221332117,1,view,100,55",  # earlier -> should sort first
        ],
    )
    df = load_events(csv)
    assert str(df["event"].dtype) == "category"
    assert str(df["transactionid"].dtype) == "Int64"
    assert df["timestamp"].is_monotonic_increasing
    assert df["visitorid"].iloc[0] == 1


def test_resolve_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("EVENTS_URL", raising=False)
    with pytest.raises(FileNotFoundError):
        resolve_data_path(tmp_path / "nope.csv")


def test_resolve_existing_file_returns_it(tmp_path):
    p = tmp_path / "events.csv"
    p.write_text("anything")
    assert resolve_data_path(p) == p


def test_sanity_report_totals(tmp_path):
    csv = tmp_path / "events.csv"
    _write_csv(
        csv,
        [
            "1433221332117,1,view,100,",
            "1433221400000,2,addtocart,200,",
            "1433221500000,2,transaction,200,9",
        ],
    )
    rep = sanity_report(load_events(csv))
    assert rep["total_rows"] == 3
    assert rep["unique_visitors"] == 2
    assert rep["event_counts"]["view"] == 1
    assert rep["event_counts"]["transaction"] == 1
