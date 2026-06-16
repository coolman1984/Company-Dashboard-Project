"""
Tests for the anomaly "guardian" engine (no pytest required).

Each test builds a focused in-memory ledger that triggers exactly one detector,
plus a clean-data test that must stay silent (no false positives).

Run:  python3 -m reports.test_anomaly
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

from . import anomaly

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

YEARS = [2024, 2025, 2026]
CURRENT = 2026

METRIC_COLS = ("net_sales", "cost_of_goods_sold", "gross_margin",
               "operating_expense", "operating_profit")


def _versions(year):
    """(version, period) coverage: prior years full Actual; 2026 outlook."""
    if year != CURRENT:
        return [("Actual", p) for p in range(1, 13)]
    return ([("Actual", p) for p in range(1, 6)] + [("T06", 6)]
            + [("T07", p) for p in range(7, 13)])


def _make_db(path, entities):
    """entities: list of dicts with dims + {year: {metric: annual_total}} under
    'values', optionally 'period_overrides': {year: {period: {metric: total}}}."""
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    dims = ("region_desc", "m_group_desc", "customer_name", "country_name")
    cols = ("year", "version", "period") + dims + METRIC_COLS
    placeholders = ", ".join("?" for _ in cols)
    rows = []
    for ent in entities:
        dim_vals = tuple(ent.get(d, "X") for d in dims)
        for year, metrics in ent["values"].items():
            vs = _versions(year)
            per_period = {m: metrics.get(m, 0) / len(vs) for m in METRIC_COLS}
            overrides = ent.get("period_overrides", {}).get(year, {})
            for version, period in vs:
                vals = dict(per_period)
                if period in overrides:
                    vals.update(overrides[period])
                rows.append((year, version, round(year + period / 1000, 3), *dim_vals,
                             *(vals[m] for m in METRIC_COLS)))
    conn.executemany(
        f"INSERT INTO pl_detail ({', '.join(cols)}) VALUES ({placeholders})", rows)
    conn.commit()
    conn.close()


def _detect(entities):
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db, entities)
        conn = sqlite3.connect(db)
        try:
            return anomaly.detect_anomalies(conn)
        finally:
            conn.close()


def _normal(group, customer, region, ns=1_000_000, gm_ratio=0.4, opex_ratio=0.2):
    """A healthy entity: stable revenue, steady margin, flat costs across 3 years."""
    vals = {}
    for y in YEARS:
        gm = ns * gm_ratio
        opex = ns * opex_ratio
        vals[y] = {"net_sales": ns, "gross_margin": gm,
                   "cost_of_goods_sold": ns - gm, "operating_expense": opex,
                   "operating_profit": gm - opex}
    return {"m_group_desc": group, "customer_name": customer,
            "region_desc": region, "values": vals}


def test_clean_data_no_anomalies():
    entities = [_normal("Alpha", "Cust A", "North"),
                _normal("Beta", "Cust B", "South")]
    found = _detect(entities)
    assert found == [], f"clean data should be silent, got {found}"


def test_first_negative_margin():
    e = _normal("Robotics", "Cust A", "North")
    # 2026 operating profit turns negative (gross margin below opex) for the first time.
    e["values"][2026] = {"net_sales": 1_000_000, "gross_margin": 100_000,
                         "cost_of_goods_sold": 900_000, "operating_expense": 250_000,
                         "operating_profit": -150_000}
    found = _detect([e, _normal("Beta", "Cust B", "South")])
    types = {a["type"] for a in found}
    assert "first_negative_margin" in types, types
    hit = next(a for a in found if a["type"] == "first_negative_margin")
    assert hit["label"] == "Robotics" and hit["severity"] == "high"
    assert hit["source"]["metric"] == "operating_profit"


def test_margin_erosion():
    e = _normal("Sensors", "Cust A", "North", gm_ratio=0.40)
    # 2026 gross margin collapses from 40% to 25% (15pp drop).
    e["values"][2026] = {"net_sales": 1_000_000, "gross_margin": 250_000,
                         "cost_of_goods_sold": 750_000, "operating_expense": 200_000,
                         "operating_profit": 50_000}
    found = _detect([e, _normal("Beta", "Cust B", "South")])
    hit = next((a for a in found if a["type"] == "margin_erosion"), None)
    assert hit is not None and hit["label"] == "Sensors"
    assert hit["detail"]["drop_pp"] >= 5.0 and hit["severity"] == "high"


def test_customer_churn():
    e = _normal("Alpha", "BigClient", "North")
    e["values"][2026] = {"net_sales": 1_000, "gross_margin": 400, "cost_of_goods_sold": 600,
                         "operating_expense": 200, "operating_profit": 200}
    found = _detect([e, _normal("Beta", "Cust B", "South")])
    hit = next((a for a in found if a["type"] == "customer_churn"), None)
    assert hit is not None and hit["label"] == "BigClient"
    assert hit["detail"]["active_prior_years"] == 2


def test_expense_spike():
    e = _normal("Alpha", "Cust A", "SpikeRegion")
    # Opex jumps 40% in 2026 while revenue stays flat.
    e["values"][2026] = {"net_sales": 1_000_000, "gross_margin": 400_000,
                         "cost_of_goods_sold": 600_000, "operating_expense": 280_000,
                         "operating_profit": 120_000}
    found = _detect([e, _normal("Beta", "Cust B", "North")])
    hit = next((a for a in found if a["type"] == "expense_spike"), None)
    assert hit is not None and hit["label"] == "SpikeRegion"
    assert hit["delta_pct"] >= 15.0


def test_period_spike():
    e = _normal("Alpha", "Cust A", "North")
    # One 2026 month has a huge operating-expense spike vs the rest.
    e["period_overrides"] = {2026: {8: {"operating_expense": 5_000_000}}}
    found = _detect([e, _normal("Beta", "Cust B", "South")])
    hit = next((a for a in found if a["type"] == "period_spike"
                and a["metric"] == "operating_expense"), None)
    assert hit is not None and hit["period"] == 8
    assert abs(hit["detail"]["z_score"]) >= 2.5


def main():
    test_clean_data_no_anomalies()
    test_first_negative_margin()
    test_margin_erosion()
    test_customer_churn()
    test_expense_spike()
    test_period_spike()
    print("anomaly tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
