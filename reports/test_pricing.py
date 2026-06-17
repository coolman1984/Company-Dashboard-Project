"""
Tests for the pricing-intelligence ("price helper") engine.

Run:  python3 -m reports.test_pricing
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

from . import pricing

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

YEARS = [2024, 2025, 2026]
CURRENT = 2026


def _versions(year):
    if year != CURRENT:
        return [("Actual", p) for p in range(1, 13)]
    return ([("Actual", p) for p in range(1, 6)] + [("T06", 6)]
            + [("T07", p) for p in range(7, 13)])


def _make_db(path, groups):
    """groups: list of {group, values:{year:{ns,gm,op}}}; customer fixed so the
    customer dimension stays neutral."""
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    cols = ("year", "version", "period", "m_group_desc", "customer_name",
            "net_sales", "gross_margin", "operating_profit")
    rows = []
    for g in groups:
        for year, m in g["values"].items():
            vs = _versions(year)
            per = {k: m[k] / len(vs) for k in ("ns", "gm", "op")}
            for version, p in vs:
                rows.append((year, version, round(year + p / 1000, 3), g["group"],
                             "Cust X", per["ns"], per["gm"], per["op"]))
    conn.executemany(
        f"INSERT INTO pl_detail ({', '.join(cols)}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()


def _healthy(group, ns=2_000_000):
    return {"group": group, "values": {y: {"ns": ns, "gm": ns * 0.40, "op": ns * 0.20}
                                        for y in YEARS}}


def _detect(groups):
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db, groups)
        conn = sqlite3.connect(db)
        try:
            return pricing.detect_pricing(conn)
        finally:
            conn.close()


def test_clean_uniform_no_suggestions():
    found = _detect([_healthy("A"), _healthy("B")])
    assert found == [], found


def test_lose_money():
    bad = {"group": "Loss", "values": {y: {"ns": 1_000_000, "gm": 100_000, "op": -50_000}
                                       for y in YEARS}}
    found = _detect([_healthy("A"), bad])
    hit = next((s for s in found if s["type"] == "lose_money"), None)
    assert hit is not None and hit["label"] == "Loss" and hit["severity"] == "high"


def test_over_discounted():
    # Below-average margin, revenue flat across years -> over-discounted.
    disc = {"group": "Discount", "values": {y: {"ns": 1_000_000, "gm": 180_000, "op": 60_000}
                                            for y in YEARS}}
    found = _detect([_healthy("A"), disc])
    hit = next((s for s in found if s["type"] == "over_discounted"), None)
    assert hit is not None and hit["label"] == "Discount"
    assert hit["gap_pp"] >= 10


def test_raise_price():
    # Below-average margin but revenue grew >=10% -> pricing power.
    hot = {"group": "Hot", "values": {
        2024: {"ns": 700_000, "gm": 140_000, "op": 50_000},
        2025: {"ns": 800_000, "gm": 160_000, "op": 60_000},
        2026: {"ns": 1_000_000, "gm": 200_000, "op": 80_000},  # +25% vs 2025, 20% margin
    }}
    found = _detect([_healthy("A"), hot])
    hit = next((s for s in found if s["type"] == "raise_price"), None)
    assert hit is not None and hit["label"] == "Hot"
    assert hit["growth_pct"] >= 10 and hit["severity"] == "opportunity"


def main():
    test_clean_uniform_no_suggestions()
    test_lose_money()
    test_over_discounted()
    test_raise_price()
    print("pricing tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
