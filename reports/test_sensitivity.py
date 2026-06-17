"""
Tests for the net-income sensitivity (tornado) engine.

Run:  python3 -m reports.test_sensitivity
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

from . import sensitivity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# One region with full 2025 outlook coverage; margin is comfortably positive.
PER_ROW = dict(net_sales=1000, cost_of_goods_sold=600, gross_margin=400,
               operating_expense=200, operating_profit=200,
               profit_before_tax=200, corporate_tax=44, net_income=156)


def _make_db(path):
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    cols = ("year", "version", "period", "region_desc") + tuple(PER_ROW)
    placeholders = ", ".join("?" for _ in cols)
    coverage = ([("Actual", p) for p in range(1, 6)] + [("T06", 6)]
                + [("T07", p) for p in range(7, 13)])
    rows = [(2025, v, round(2025 + p / 1000, 3), "Asia Pacific", *PER_ROW.values())
            for v, p in coverage]
    conn.executemany(
        f"INSERT INTO pl_detail ({', '.join(cols)}) VALUES ({placeholders})", rows)
    conn.commit()
    conn.close()


def _run(delta=5.0):
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db)
        conn = sqlite3.connect(db)
        try:
            return sensitivity.run_sensitivity(conn, delta_pct=delta)
        finally:
            conn.close()


def test_three_drivers_present_and_ranked():
    rows, extra = _run()
    assert {r["driver"] for r in rows} == {"net_sales", "cost_of_goods_sold", "operating_expense"}
    # sorted by absolute swing, descending
    swings = [abs(r["swing"]) for r in rows]
    assert swings == sorted(swings, reverse=True)
    assert extra["most_sensitive"] == rows[0]["driver"]


def test_driver_directions():
    rows, _extra = _run()
    by = {r["driver"]: r for r in rows}
    # More revenue lifts net income; more cost lowers it.
    assert by["net_sales"]["ni_high"] > by["net_sales"]["ni_low"]
    assert by["cost_of_goods_sold"]["ni_high"] < by["cost_of_goods_sold"]["ni_low"]
    assert by["operating_expense"]["ni_high"] < by["operating_expense"]["ni_low"]


def test_zero_delta_is_flat():
    rows, _extra = _run(delta=0.0)
    for r in rows:
        assert abs(r["swing"]) < 1e-6, r


def main():
    test_three_drivers_present_and_ranked()
    test_driver_directions()
    test_zero_delta_is_flat()
    print("sensitivity tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
