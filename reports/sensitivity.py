"""
sensitivity.py - "which lever moves profit the most?" (tornado analysis).

This is a thin analytical layer **on top of the what-if engine** (`scenario.py`):
for each controllable driver it nudges the assumption down and up by the same
percentage and measures the resulting swing in net income. Ranking the swings
answers the question every CFO asks before a planning meeting — *where is my
profit most exposed?* — without the user having to drag every slider by hand.

It reuses `scenario.run_scenario` rather than re-deriving any P&L maths, so the
numbers always agree with the interactive what-if panel. Deterministic, offline,
unit-tested.

Usage:
    python3 -m reports.sensitivity                 # human summary
    python3 -m reports.sensitivity --json          # machine JSON (dashboard)
    python3 -m reports.sensitivity --delta 10      # ±10% instead of ±5%
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

from . import scenario

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")

# The drivers we flex, with display labels. These are exactly the levers the
# interactive what-if panel exposes, so the two views stay consistent.
DRIVERS = [
    ("net_sales", "Net sales"),
    ("cost_of_goods_sold", "COGS"),
    ("operating_expense", "Operating expense"),
]


def _net_income(conn, config):
    _cols, rows, _extra = scenario.run_scenario(conn, config)
    for row in rows:
        if row["line_item"] == "Net Income":
            return row["scenario"]
    return 0.0


def run_sensitivity(conn, delta_pct=5.0, tax_rate=scenario.DEFAULT_TAX_RATE,
                    cogs_scales_with_revenue=True):
    """Return (rows, extra). Each row: driver, ni_low, ni_high, base, swing."""
    base = {"name": "base", "adjustments": [], "tax_rate": tax_rate,
            "cogs_scales_with_revenue": cogs_scales_with_revenue}
    ni_base = _net_income(conn, base)

    rows = []
    for metric, label in DRIVERS:
        def cfg(change):
            return {"name": label, "tax_rate": tax_rate,
                    "cogs_scales_with_revenue": cogs_scales_with_revenue,
                    "adjustments": [{"metric": metric, "change_pct": change}]}
        ni_low = _net_income(conn, cfg(-delta_pct))
        ni_high = _net_income(conn, cfg(+delta_pct))
        swing = ni_high - ni_low
        rows.append({
            "driver": metric,
            "label": label,
            "base": ni_base,
            "ni_low": ni_low,
            "ni_high": ni_high,
            "swing": swing,
            "swing_pct": round(swing / abs(ni_base) * 100, 2) if ni_base else None,
        })
    rows.sort(key=lambda r: -abs(r["swing"]))
    extra = {"delta_pct": delta_pct, "base_net_income": ni_base,
             "most_sensitive": rows[0]["driver"] if rows else None}
    return rows, extra


def build_report(db_path=DEFAULT_DB, delta_pct=5.0):
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it or load client data first.")
    conn = sqlite3.connect(db_path)
    try:
        rows, extra = run_sensitivity(conn, delta_pct=delta_pct)
    finally:
        conn.close()
    return {"columns": ["driver", "label", "base", "ni_low", "ni_high", "swing", "swing_pct"],
            "rows": rows, **extra}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Net-income sensitivity (tornado) analysis.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Source database.")
    parser.add_argument("--delta", type=float, default=5.0, help="± percent shock per driver.")
    parser.add_argument("--json", action="store_true", help="Print machine JSON.")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.db, delta_pct=args.delta)
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0
    print(f"Net-income sensitivity (±{report['delta_pct']}%), base = {report['base_net_income']:.0f}")
    for r in report["rows"]:
        print(f"  {r['label']:20} swing={r['swing']:>14,.0f}  "
              f"[{r['ni_low']:,.0f} .. {r['ni_high']:,.0f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
