"""
Self-contained tests for map_raw_to_db.py (no pytest required).

Run:  python3 test_map_raw_to_db.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile

import map_raw_to_db as m


def _write_capture(raw_dir, filename, sheet_name, header, rows):
    """Write a spreadsheet raw-JSON capture shaped like the extractor's output."""
    os.makedirs(raw_dir, exist_ok=True)
    envelope = {
        "schema_version": 1,
        "source": {"filename": filename, "relpath": filename},
        "extractor": "excel-openpyxl",
        "document_type": "spreadsheet",
        "content": {"sheets": [{
            "name": sheet_name,
            "n_rows": len(rows) + 1,
            "n_cols": len(header),
            "cells": [header] + rows,
        }]},
        "warnings": [],
    }
    with open(os.path.join(raw_dir, filename), "w", encoding="utf-8") as fh:
        json.dump(envelope, fh)


def _base_mapping():
    return {
        "name": "test",
        "source_glob": "*PL*.raw.json",
        "sheet": "Ledger",
        "header_row": 0,
        "skip_blank_rows": True,
        "columns": {
            "Year": "year", "Version": "version", "Period": "period",
            "Region": "region_desc", "Net Sales": "net_sales",
        },
        "constants": {"currency": "USD"},
    }


HEADER = ["Year", "Version", "Period", "Region", "Net Sales"]


def _expect_error(fn, needle):
    try:
        fn()
    except m.MappingError as err:
        assert needle.lower() in str(err).lower(), f"got: {err}"
        return
    raise AssertionError(f"expected MappingError containing {needle!r}")


def test_dry_run_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw")
        db = os.path.join(tmp, "pl_detail.db")
        mp = os.path.join(tmp, "map.json")
        _write_capture(raw, "client_PL.raw.json", "Ledger", HEADER, [
            [2025, "Actual", 3, "Africa", "1,250,000"],  # comma + bare period
            [None, None, None, None, None],               # blank row -> skipped
            [2025, "Actual", 2026.004, "Europe", 980000], # already encoded? -> invalid yr
        ])
        # Fix the third row to a valid encoded period for the happy path.
        _write_capture(raw, "client_PL.raw.json", "Ledger", HEADER, [
            [2025, "Actual", 3, "Africa", "1,250,000"],
            [None, None, None, None, None],
            [2025, "T07", 2025.011, "Europe", 980000],
        ])
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(_base_mapping(), fh)

        dry = m.load(mp, raw_dir=raw, db_path=db, dry_run=True, verbose=False)
        assert dry["rows_read"] == 2, dry          # blank row skipped
        assert not os.path.exists(db), "dry run must not write a database"

        stats = m.load(mp, raw_dir=raw, db_path=db, verbose=False)
        assert stats["rows_inserted"] == 2, stats

        conn = sqlite3.connect(db)
        try:
            rows = conn.execute(
                "SELECT year, version, period, region_desc, net_sales, currency "
                "FROM pl_detail ORDER BY region_desc").fetchall()
            assert rows[0] == (2025, "Actual", 2025.003, "Africa", 1250000.0, "USD"), rows[0]
            assert rows[1][2] == 2025.011 and rows[1][1] == "T07", rows[1]
            # numeric conversion: net_sales stored as REAL
            assert isinstance(rows[0][4], float)
            # constant applied
            assert rows[0][5] == "USD"
            # canonical view + index restored after bulk load
            assert conn.execute("SELECT COUNT(*) FROM v_yearly_pl").fetchone()[0] >= 1
            idx = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_year'"
            ).fetchone()
            assert idx is not None, "indexes should exist after load"
        finally:
            conn.close()


def test_multiple_batches():
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw")
        db = os.path.join(tmp, "pl_detail.db")
        mp = os.path.join(tmp, "map.json")
        rows = [[2025, "Actual", (i % 12) + 1, "Africa", 1000 + i] for i in range(5)]
        _write_capture(raw, "batch_PL.raw.json", "Ledger", HEADER, rows)
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(_base_mapping(), fh)
        stats = m.load(mp, raw_dir=raw, db_path=db, batch_size=2, verbose=False)
        assert stats["rows_inserted"] == 5, stats
        assert stats["batches"] == 3, stats  # 2 + 2 + 1


def test_overwrite_protection_and_force_preserves_on_failure():
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw")
        db = os.path.join(tmp, "pl_detail.db")
        mp = os.path.join(tmp, "map.json")
        _write_capture(raw, "ok_PL.raw.json", "Ledger", HEADER,
                       [[2025, "Actual", 1, "Africa", 100]])
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(_base_mapping(), fh)

        m.load(mp, raw_dir=raw, db_path=db, verbose=False)
        assert os.path.exists(db)

        # Without --force, refuse to overwrite.
        _expect_error(lambda: m.load(mp, raw_dir=raw, db_path=db, verbose=False),
                      "already exists")

        # A forced load that fails mid-way must leave the original DB intact.
        before = open(db, "rb").read()
        _write_capture(raw, "bad_PL.raw.json", "Ledger", HEADER,
                       [[2025, "BADVERSION", 1, "Africa", 100]])
        _expect_error(
            lambda: m.load(mp, raw_dir=raw, db_path=db, force=True, verbose=False),
            "version")
        assert open(db, "rb").read() == before, "failed forced load corrupted the DB"
        leftovers = [f for f in os.listdir(tmp) if f.startswith(".pl_detail.")]
        assert not leftovers, f"temp files left behind: {leftovers}"


def test_post_load_validation_aborts_on_duplicate_grain():
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw")
        db = os.path.join(tmp, "pl_detail.db")
        mp = os.path.join(tmp, "map.json")
        # Two rows with an identical grain (same year/version/period/region;
        # country/customer/product all NULL) -> ambiguous, must be rejected.
        _write_capture(raw, "dup_PL.raw.json", "Ledger", HEADER, [
            [2025, "Actual", 1, "Africa", 100],
            [2025, "Actual", 1, "Africa", 200],
        ])
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(_base_mapping(), fh)

        _expect_error(
            lambda: m.load(mp, raw_dir=raw, db_path=db, verbose=False),
            "validation")
        assert not os.path.exists(db), "failed validation must not write a database"
        leftovers = [f for f in os.listdir(tmp) if f.startswith(".pl_detail.")]
        assert not leftovers, f"temp files left behind: {leftovers}"


def test_mapping_validation():
    cols = m.load_schema_columns()

    bad = _base_mapping(); bad["columns"]["Net Sales 2"] = "net_sales"
    _expect_error(lambda: m.validate_mapping(bad, cols), "duplicate")

    unknown = _base_mapping(); unknown["columns"]["Mystery"] = "not_a_column"
    _expect_error(lambda: m.validate_mapping(unknown, cols), "unknown")

    missing = _base_mapping(); del missing["columns"]["Period"]
    _expect_error(lambda: m.validate_mapping(missing, cols), "period")

    no_glob = _base_mapping(); del no_glob["source_glob"]
    _expect_error(lambda: m.validate_mapping(no_glob, cols), "source_glob")


def main():
    test_dry_run_and_load()
    test_multiple_batches()
    test_overwrite_protection_and_force_preserves_on_failure()
    test_post_load_validation_aborts_on_duplicate_grain()
    test_mapping_validation()
    print("map_raw_to_db tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
