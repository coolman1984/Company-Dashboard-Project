"""
Self-contained tests for the reports engine (no pytest required).

Builds a small database from schema.sql, generates reports, and checks the
JSON envelope and CSV output.

Run:  python3 -m reports.test_reports
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile

from .definitions import REPORTS
from .generate import generate

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def _make_db(path):
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    rows = [
        # year, version, period, region, net_sales, gross_margin, operating_profit, net_income
        (2024, "Actual", 2024.001, "Africa", 1000.0, 400.0, 200.0, 150.0),
        (2025, "Actual", 2025.001, "Africa", 1200.0, 480.0, 240.0, 180.0),
        (2025, "Actual", 2025.001, "Europe", 800.0, 300.0, 150.0, 110.0),
        (2026, "T07", 2026.007, "Africa", 999.0, 0.0, 0.0, 0.0),  # non-Actual: excluded from views
    ]
    conn.executemany(
        "INSERT INTO pl_detail (year, version, period, region_desc, net_sales, "
        "gross_margin, operating_profit, net_income) VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        out = os.path.join(tmp, "reports")
        _make_db(db)

        results = generate(db, out, formats=("json", "csv"), verbose=False)
        assert len(results) == len(REPORTS), results

        # Every report produced a JSON + CSV file.
        for report in REPORTS:
            assert os.path.exists(os.path.join(out, f"{report.name}.json"))
            assert os.path.exists(os.path.join(out, f"{report.name}.csv"))

        # Inspect the yearly P&L envelope.
        with open(os.path.join(out, "yearly_pl.json"), encoding="utf-8") as fh:
            env = json.load(fh)
        assert env["report"] == "yearly_pl"
        assert env["title"] == "Yearly P&L Summary"
        assert env["generated_at"].endswith("Z")
        assert env["source"]["rows_in_ledger"] == 4  # all rows, incl. non-Actual
        assert env["row_count"] == len(env["rows"])
        years = [r["year"] for r in env["rows"]]
        assert years == [2024, 2025], years  # views are Actual-only; T07 excluded
        y2025 = next(r for r in env["rows"] if r["year"] == 2025)
        assert y2025["net_sales"] == 2000.0, y2025  # Africa 1200 + Europe 800

        # Single-report selection works.
        single = generate(db, out, names=["regional_pl"], formats=("json",), verbose=False)
        assert len(single) == 1 and single[0]["report"] == "regional_pl"

    print("reports tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
