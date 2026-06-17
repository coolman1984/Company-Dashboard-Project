"""
Tests for the offline natural-language query parser (no pytest required).

Run:  python3 -m reports.test_nlquery
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

from . import nlquery

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

VOCAB = {
    "region_desc": ["Africa", "Asia Pacific", "Europe"],
    "country_name": ["Kenya", "Japan"],
    "m_group_desc": ["Robotics", "Sensors"],
    "customer_name": ["Acme Corp"],
    "years": [2024, 2025, 2026],
}
CURRENT = 2026


def test_metric_detection():
    assert nlquery.parse("net sales by region", VOCAB, CURRENT)["metric"] == "net_sales"
    assert nlquery.parse("gross margin", VOCAB, CURRENT)["metric"] == "gross_margin"
    assert nlquery.parse("show operating expense", VOCAB, CURRENT)["metric"] == "operating_expense"
    # Arabic
    assert nlquery.parse("المصروفات التشغيلية حسب المنطقة", VOCAB, CURRENT)["metric"] == "operating_expense"
    assert nlquery.parse("مبيعات أفريقيا", VOCAB, CURRENT)["metric"] == "net_sales"


def test_group_by_and_year():
    q = nlquery.parse("net sales by region", VOCAB, CURRENT)
    assert q["group_by"] == "region_desc"
    assert q["year"] == CURRENT
    q2 = nlquery.parse("revenue by product in 2024", VOCAB, CURRENT)
    assert q2["group_by"] == "m_group_desc" and q2["year"] == 2024
    q3 = nlquery.parse("net income last year", VOCAB, CURRENT)
    assert q3["year"] == CURRENT - 1


def test_comparison_sets_group_and_filters():
    q = nlquery.parse("compare Africa vs Asia Pacific net sales", VOCAB, CURRENT)
    assert q["group_by"] == "region_desc"
    assert set(q["filters"]["region_desc"]) == {"Africa", "Asia Pacific"}
    assert q["compare"] is True


def test_single_entity_is_filter_not_group():
    q = nlquery.parse("show me Africa sales in 2025", VOCAB, CURRENT)
    assert q["group_by"] is None
    assert q["filters"]["region_desc"] == ["Africa"]
    assert q["year"] == 2025


def test_quarter():
    assert nlquery.parse("gross margin first quarter", VOCAB, CURRENT)["periods"] == [1, 2, 3]
    assert nlquery.parse("sales الربع الرابع", VOCAB, CURRENT)["periods"] == [10, 11, 12]


def _make_db(path):
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    cols = ("year", "version", "period", "region_desc", "net_sales", "gross_margin")
    rows = []
    for region, ns in (("Africa", 100), ("Asia Pacific", 300)):
        for p in range(1, 13):
            rows.append((2026, "Actual" if p <= 5 else ("T06" if p == 6 else "T07"),
                         round(2026 + p / 1000, 3), region, ns, ns * 0.4))
    conn.executemany(
        f"INSERT INTO pl_detail ({', '.join(cols)}) VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()


def test_run_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        _make_db(db)
        conn = sqlite3.connect(db)
        try:
            result = nlquery.run(conn, "net sales by region")
        finally:
            conn.close()
        by_label = {r["label"]: r["value"] for r in result["rows"]}
        assert by_label["Asia Pacific"] == 300 * 12
        assert by_label["Africa"] == 100 * 12
        assert "by region" in result["interpretation"]


def main():
    test_metric_detection()
    test_group_by_and_year()
    test_comparison_sets_group_and_filters()
    test_single_entity_is_filter_not_group()
    test_quarter()
    test_run_end_to_end()
    print("nlquery tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
