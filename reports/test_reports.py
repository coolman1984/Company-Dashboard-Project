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


def _make_outlook_db(path):
    """Prior year (2024) full actual + current year (2025) Actual+T06+T07."""
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    rows = []
    for p in range(1, 13):  # 2024 actual full -> net_sales total 1000
        rows.append((2024, "Actual", round(2024 + p / 1000, 3), "Africa",
                     1000 / 12, 400 / 12, 200 / 12, 150 / 12))
    for p in range(1, 6):   # 2025 Actual P01-05 (500)
        rows.append((2025, "Actual", round(2025 + p / 1000, 3), "Africa", 100, 40, 20, 15))
    rows.append((2025, "T06", 2025.006, "Africa", 100, 40, 20, 15))  # T06 P06 (100)
    for p in range(7, 13):  # T07 P07-12 (600)
        rows.append((2025, "T07", round(2025 + p / 1000, 3), "Africa", 100, 40, 20, 15))
    conn.executemany(
        "INSERT INTO pl_detail (year, version, period, region_desc, net_sales, "
        "gross_margin, operating_profit, net_income) VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_csv_has_bom_and_preserves_arabic():
    """CSV exports must carry a UTF-8 BOM and keep Arabic text intact."""
    from .generate import write_csv
    envelope = {
        "report": "regional_pl_ar",
        "columns": ["المنطقة", "net_sales"],
        "rows": [{"المنطقة": "أفريقيا", "net_sales": 1200.0}],
    }
    with tempfile.TemporaryDirectory() as out:
        path = write_csv(envelope, out)
        with open(path, "rb") as fh:
            raw = fh.read()
        assert raw.startswith(b"\xef\xbb\xbf"), "CSV should start with a UTF-8 BOM"
        text = raw.decode("utf-8-sig")
        assert "أفريقيا" in text and "المنطقة" in text, text


def test_outlook_reports():
    from .generate import compute_envelopes
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_outlook_db(db)
        envs = {e["report"]: e for e in compute_envelopes(db)}

        pl = envs["outlook_pl"]
        assert pl["basis"] == "FY2025 full-year outlook vs FY2024 actual", pl.get("basis")
        net = next(r for r in pl["rows"] if r["line_item"] == "Net Sales")
        assert round(net["outlook"]) == 1200, net      # 500 + 100 + 600
        assert round(net["prior_year"]) == 1000, net
        assert round(net["variance"]) == 200, net
        assert net["variance_pct"] == 20.0, net

        monthly = envs["outlook_monthly"]
        assert monthly["row_count"] == 12, monthly["row_count"]
        statuses = [r["status"] for r in monthly["rows"]]
        assert statuses.count("actual") == 5 and statuses.count("outlook") == 7, statuses


def main():
    test_csv_has_bom_and_preserves_arabic()
    test_outlook_reports()
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
