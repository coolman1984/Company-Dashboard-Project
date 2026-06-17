"""
pricing.py - the "price helper": deterministic pricing intelligence.

For every product group and customer it compares margin and growth against the
company average and recommends a concrete action:

  * lose_money     - operating profit is negative -> reprice or exit.
  * over_discounted - gross margin sits well below the company average -> the
    discount/price is leaking margin.
  * raise_price     - revenue is growing but margin is thin -> demand is there,
    so there is room to raise price.

Like the rest of the engines this is **offline, deterministic and
source-traceable** (every suggestion carries year/dimension/label) — a finance
user must be able to ask "why are you telling me to do this?" and get a rule, not
a guess. Reuses the outlook coverage convention.

Usage:
    python3 -m reports.pricing                 # human summary
    python3 -m reports.pricing --json          # machine JSON (dashboard)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

from .outlook import detect_years, _outlook_where

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")

MIN_REVENUE_FRACTION = 0.01    # ignore items below 1% of total revenue
OVER_DISCOUNT_GAP_PP = 10.0    # margin this far below average = a pricing problem
GROWTH_PCT = 10.0              # revenue growth that signals pricing power

DIMENSIONS = [("m_group_desc", "product group"), ("customer_name", "customer")]


def _dim_totals(conn, dimension, year, current):
    if year == current:
        wsql, wp = _outlook_where(conn, year)
    else:
        wsql, wp = "year = ? AND version = 'Actual'", (year,)
    sql = (f"SELECT COALESCE({dimension}, 'Unassigned') AS label, "
           f"COALESCE(SUM(net_sales), 0), COALESCE(SUM(gross_margin), 0), "
           f"COALESCE(SUM(operating_profit), 0) FROM pl_detail WHERE {wsql} GROUP BY {dimension}")
    return {r[0]: {"ns": r[1], "gm": r[2], "op": r[3]} for r in conn.execute(sql, wp)}


def _suggestion(type_, severity, dimension, label, *, net_sales, gm_pct,
                operating_profit, company_avg_pct, gap_pp=None, growth_pct=None):
    return {
        "type": type_,
        "severity": severity,
        "dimension": dimension,
        "label": label,
        "net_sales": net_sales,
        "gross_margin_pct": round(gm_pct, 2),
        "operating_profit": operating_profit,
        "company_avg_pct": round(company_avg_pct, 2),
        "gap_pp": round(gap_pp, 2) if gap_pp is not None else None,
        "growth_pct": round(growth_pct, 2) if growth_pct is not None else None,
        "source": {"year": None, "dimension": dimension, "label": label,
                   "metric": "gross_margin"},
    }


def detect_pricing(conn):
    current, prior = detect_years(conn)
    if current is None:
        return []
    suggestions = []
    for dimension, _label in DIMENSIONS:
        cur = _dim_totals(conn, dimension, current, current)
        pri = _dim_totals(conn, dimension, prior, current) if prior is not None else {}
        total_ns = sum(v["ns"] for v in cur.values())
        total_gm = sum(v["gm"] for v in cur.values())
        avg_pct = (total_gm / total_ns * 100) if total_ns else 0.0
        min_abs = abs(total_ns) * MIN_REVENUE_FRACTION

        for label, v in cur.items():
            ns, gm, op = v["ns"], v["gm"], v["op"]
            if ns <= 0:
                continue
            gm_pct = gm / ns * 100
            if op < 0:
                s = _suggestion("lose_money", "high", dimension, label, net_sales=ns,
                                gm_pct=gm_pct, operating_profit=op, company_avg_pct=avg_pct)
                s["source"]["year"] = current
                suggestions.append(s)
            elif ns > min_abs and gm_pct < avg_pct - OVER_DISCOUNT_GAP_PP:
                prior_ns = pri.get(label, {}).get("ns", 0)
                growth = ((ns - prior_ns) / prior_ns * 100) if prior_ns > 0 else None
                if growth is not None and growth >= GROWTH_PCT:
                    s = _suggestion("raise_price", "opportunity", dimension, label,
                                    net_sales=ns, gm_pct=gm_pct, operating_profit=op,
                                    company_avg_pct=avg_pct, gap_pp=avg_pct - gm_pct,
                                    growth_pct=growth)
                else:
                    s = _suggestion("over_discounted", "medium", dimension, label,
                                    net_sales=ns, gm_pct=gm_pct, operating_profit=op,
                                    company_avg_pct=avg_pct, gap_pp=avg_pct - gm_pct)
                s["source"]["year"] = current
                suggestions.append(s)

    rank = {"high": 0, "medium": 1, "opportunity": 2}
    suggestions.sort(key=lambda s: (rank.get(s["severity"], 9), -abs(s["net_sales"])))
    return suggestions


def build_report(db_path=DEFAULT_DB):
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it or load client data first.")
    conn = sqlite3.connect(db_path)
    try:
        current, _prior = detect_years(conn)
        suggestions = detect_pricing(conn)
    finally:
        conn.close()
    by_action = {}
    for s in suggestions:
        by_action[s["type"]] = by_action.get(s["type"], 0) + 1
    return {"year": current, "count": len(suggestions),
            "by_action": by_action, "suggestions": suggestions}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pricing intelligence over the ledger.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Source database.")
    parser.add_argument("--json", action="store_true", help="Print machine JSON.")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.db)
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0
    print(f"FY{report['year']} pricing: {report['count']} suggestion(s) {report['by_action']}")
    for s in report["suggestions"]:
        print(f"  [{s['severity']:11}] {s['type']:15} {s['dimension']}={s['label']:24} "
              f"GM%={s['gross_margin_pct']:.1f} (avg {s['company_avg_pct']:.1f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
