"""
Tests for the what-if scenario engine (no pytest required).

Run:  python3 -m reports.test_scenario
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

from . import scenario

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# Two regions, each with full 2025 outlook coverage (12 period-rows), identical
# per-row figures so the maths is easy to verify.
PER_ROW = dict(net_sales=100, cost_of_goods_sold=60, gross_margin=40,
               operating_expense=20, operating_profit=20,
               profit_before_tax=20, corporate_tax=4.4, net_income=15.6)


def _make_db(path):
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    cols = ("year", "version", "period", "region_desc") + tuple(PER_ROW)
    placeholders = ", ".join("?" for _ in cols)
    rows = []

    def coverage():
        return ([("Actual", p) for p in range(1, 6)] + [("T06", 6)]
                + [("T07", p) for p in range(7, 13)])

    for region in ("Asia Pacific", "Africa"):
        for version, p in coverage():
            rows.append((2025, version, round(2025 + p / 1000, 3), region,
                         *PER_ROW.values()))
    conn.executemany(
        f"INSERT INTO pl_detail ({', '.join(cols)}) VALUES ({placeholders})", rows)
    conn.commit()
    conn.close()


def _lines(rows):
    return {r["line_item"]: r for r in rows}


def test_zero_adjustment_reproduces_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db)
        conn = sqlite3.connect(db)
        try:
            _cols, rows, _extra = scenario.run_scenario(conn, {"name": "Flat", "adjustments": []})
        finally:
            conn.close()
        for row in rows:
            assert row["change"] == 0, row
            assert row["baseline"] == row["scenario"], row
        # 24 rows x 100 net sales = 2400 baseline.
        assert _lines(rows)["Net Sales"]["baseline"] == 2400


def test_regional_revenue_cut():
    config = {
        "name": "AP down 10%",
        "cogs_scales_with_revenue": True,
        "tax_rate": 0.22,
        "adjustments": [
            {"metric": "net_sales", "change_pct": -10, "where": {"region_desc": "Asia Pacific"}},
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db)
        conn = sqlite3.connect(db)
        try:
            _cols, rows, extra = scenario.run_scenario(conn, config)
        finally:
            conn.close()
        lines = _lines(rows)
        # Asia Pacific net sales = 1200; -10% = -120 across 2400 baseline.
        assert lines["Net Sales"]["change"] == -120, lines["Net Sales"]
        assert lines["Net Sales"]["scenario"] == 2280
        # COGS scales with revenue: AP cogs 720 -> -72.
        assert round(lines["COGS"]["change"], 2) == -72.0, lines["COGS"]
        # Gross margin delta = -120 - (-72) = -48.
        assert round(lines["Gross Margin"]["change"], 2) == -48.0, lines["Gross Margin"]
        # Net income delta = -48 * (1 - 0.22) = -37.44.
        assert round(lines["Net Income"]["change"], 2) == -37.44, lines["Net Income"]
        assert extra["scenario_name"] == "AP down 10%"


def test_validation():
    for bad, needle in [
        ({"adjustments": [{"metric": "ebitda", "change_pct": 1}]}, "metric"),
        ({"adjustments": [{"metric": "net_sales", "change_pct": "lots"}]}, "change_pct"),
        ({"adjustments": [{"metric": "net_sales", "change_pct": 1, "where": {"colour": "red"}}]}, "filter"),
        ({"tax_rate": 2}, "tax_rate"),
    ]:
        try:
            scenario.validate_scenario(bad)
        except scenario.ScenarioError as err:
            assert needle in str(err).lower(), err
        else:
            raise AssertionError(f"expected ScenarioError for {bad}")


def test_evaluate_config_json_ready():
    # The interactive dashboard endpoint goes through evaluate_config; it must
    # return a JSON-ready dict and reproduce the baseline for a no-op scenario.
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db)
        result = scenario.evaluate_config(db, {"name": "Flat", "adjustments": []})
        assert set(result) >= {"columns", "rows", "basis", "scenario_name"}, result
        lines = _lines(result["rows"])
        assert lines["Net Income"]["change"] == 0
        # A real lever moves net income.
        lifted = scenario.evaluate_config(
            db, {"name": "Up", "adjustments": [{"metric": "net_sales", "change_pct": 10}]})
        assert _lines(lifted["rows"])["Net Income"]["change"] > 0


def test_compare_side_by_side():
    scenarios = [
        {"name": "Conservative", "adjustments": [{"metric": "net_sales", "change_pct": -10}]},
        {"name": "Base", "adjustments": []},
        {"name": "Aggressive", "adjustments": [{"metric": "net_sales", "change_pct": 10}]},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db)
        conn = sqlite3.connect(db)
        try:
            result = scenario.compare(conn, scenarios)
        finally:
            conn.close()
        assert result["scenarios"] == ["Conservative", "Base", "Aggressive"]
        assert result["columns"] == ["line_item", "baseline", "Conservative", "Base", "Aggressive"]
        ns = next(r for r in result["rows"] if r["line_item"] == "Net Sales")
        # Base reproduces the baseline; Conservative < baseline < Aggressive.
        assert ns["Base"] == ns["baseline"]
        assert ns["Conservative"] < ns["baseline"] < ns["Aggressive"]


def main():
    test_zero_adjustment_reproduces_baseline()
    test_regional_revenue_cut()
    test_validation()
    test_evaluate_config_json_ready()
    test_compare_side_by_side()
    print("scenario tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
