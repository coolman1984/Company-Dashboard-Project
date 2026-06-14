"""
scenario.py - what-if scenario modelling on top of the baseline outlook.

A scenario is a small, reviewable JSON file of assumption changes ("levers")
applied to the forecast outlook, producing a baseline-vs-scenario P&L so
management can see the impact of a decision before taking it. Example levers:
  * "Asia Pacific net sales -10%"
  * "Robotics net sales +5%"
  * "operating expense +3% across the board"

Model (transparent and zero-adjustment-safe):
  * Only the controllable lines are adjusted directly: net sales, COGS, opex.
  * COGS optionally scales with revenue volume (cogs_scales_with_revenue).
  * Downstream lines move by identity on the *delta*, so a scenario with no
    adjustments reproduces the baseline exactly:
        d_gross_margin     = d_net_sales - d_cogs
        d_operating_profit = d_gross_margin - d_opex
        d_pbt              = d_operating_profit
        d_tax              = d_pbt * tax_rate         (flat marginal rate)
        d_net_income       = d_pbt - d_tax
  * Each scenario line = baseline line + its delta.

Usage:
    python3 -m reports.scenario --scenario scenario.example.json
    python3 -m reports.scenario --scenario s.json --format json xlsx pdf
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

from . import generate, outlook, render

DRIVERS = ("net_sales", "cost_of_goods_sold", "operating_expense")
DIM_COLS = ("region_desc", "country_name", "m_group_desc", "customer_name", "class")
DEFAULT_TAX_RATE = 0.22

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")
DEFAULT_OUT = os.path.join(BASE_DIR, "output", "reports")


class ScenarioError(Exception):
    """A malformed scenario the operator must fix."""


def load_scenario(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError:
        raise ScenarioError(f"Scenario file not found: {path}")
    except json.JSONDecodeError as error:
        raise ScenarioError(f"Scenario file is not valid JSON: {error}")
    validate_scenario(config)
    return config


def validate_scenario(config):
    if not isinstance(config, dict):
        raise ScenarioError("Scenario must be a JSON object.")
    adjustments = config.get("adjustments", [])
    if not isinstance(adjustments, list):
        raise ScenarioError("'adjustments' must be a list.")
    for i, adj in enumerate(adjustments):
        where = f"adjustment {i}"
        if adj.get("metric") not in DRIVERS:
            raise ScenarioError(f"{where}: 'metric' must be one of {DRIVERS}.")
        if not isinstance(adj.get("change_pct"), (int, float)):
            raise ScenarioError(f"{where}: 'change_pct' must be a number.")
        bad = [k for k in (adj.get("where") or {}) if k not in DIM_COLS]
        if bad:
            raise ScenarioError(f"{where}: unknown filter column(s) {bad}; "
                                f"use any of {DIM_COLS}.")
    rate = config.get("tax_rate", DEFAULT_TAX_RATE)
    if not isinstance(rate, (int, float)) or not (0 <= rate < 1):
        raise ScenarioError("'tax_rate' must be a number in [0, 1).")


def _matches(row, where):
    return all(row.get(k) == v for k, v in (where or {}).items())


def _factor(row, metric, adjustments):
    factor = 1.0
    for adj in adjustments:
        if adj["metric"] == metric and _matches(row, adj.get("where")):
            factor *= 1 + adj["change_pct"] / 100.0
    return factor


def run_scenario(conn, config):
    """Return (columns, rows, extra): baseline vs scenario by P&L line."""
    year, _prior = outlook.detect_years(conn)
    columns = ["line_item", "baseline", "scenario", "change", "change_pct"]
    if year is None:
        return columns, [], {"basis": "no data"}

    where_sql, params = outlook._outlook_where(conn, year)
    base = outlook._sum_lines(conn, where_sql, params)

    adjustments = config.get("adjustments", [])
    scales = config.get("cogs_scales_with_revenue", True)
    tax_rate = float(config.get("tax_rate", DEFAULT_TAX_RATE))

    colnames = DIM_COLS + DRIVERS
    select = ", ".join(colnames)
    sums = {"ns": 0.0, "cogs": 0.0, "opex": 0.0}
    adj = {"ns": 0.0, "cogs": 0.0, "opex": 0.0}
    for raw in conn.execute(f"SELECT {select} FROM pl_detail WHERE {where_sql}", params):
        row = dict(zip(colnames, raw))
        ns = row["net_sales"] or 0
        cogs = row["cost_of_goods_sold"] or 0
        opex = row["operating_expense"] or 0
        ns_f = _factor(row, "net_sales", adjustments)
        cogs_f = (ns_f if scales else 1.0) * _factor(row, "cost_of_goods_sold", adjustments)
        opex_f = _factor(row, "operating_expense", adjustments)
        sums["ns"] += ns; sums["cogs"] += cogs; sums["opex"] += opex
        adj["ns"] += ns * ns_f; adj["cogs"] += cogs * cogs_f; adj["opex"] += opex * opex_f

    d_ns = adj["ns"] - sums["ns"]
    d_cogs = adj["cogs"] - sums["cogs"]
    d_opex = adj["opex"] - sums["opex"]
    d_gm = d_ns - d_cogs
    d_op = d_gm - d_opex
    d_pbt = d_op
    d_tax = d_pbt * tax_rate
    d_ni = d_pbt - d_tax
    delta = {
        "net_sales": d_ns, "cost_of_goods_sold": d_cogs, "gross_margin": d_gm,
        "operating_expense": d_opex, "operating_profit": d_op,
        "profit_before_tax": d_pbt, "corporate_tax": d_tax, "net_income": d_ni,
    }

    rows = []
    for label, col in outlook.PL_LINES:
        b = base.get(col, 0) or 0
        d = delta.get(col, 0.0)
        s = b + d
        rows.append({"line_item": label, "baseline": b, "scenario": s,
                     "change": d, "change_pct": round(d / abs(b) * 100, 2) if b else None})
    extra = {"basis": f"FY{year} scenario vs baseline outlook",
             "scenario_name": config.get("name", "Scenario")}
    return columns, rows, extra


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "scenario"


def generate_scenario(db_path, scenario_path, out_dir,
                      formats=("json", "xlsx", "pdf"), verbose=True):
    config = load_scenario(scenario_path)
    generate._check_formats(formats)
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it or load client data first.")

    conn = sqlite3.connect(db_path)
    try:
        ledger_rows = conn.execute("SELECT COUNT(*) FROM pl_detail").fetchone()[0]
        columns, rows, extra = run_scenario(conn, config)
    finally:
        conn.close()

    name = "scenario_" + _slug(config.get("name", "scenario"))
    envelope = {
        "report": name,
        "title": f"Scenario: {config.get('name', 'Scenario')}",
        "description": config.get("description", ""),
        "generated_at": generate._utc_now_iso(),
        "source": {"database": os.path.basename(db_path), "rows_in_ledger": ledger_rows},
        "columns": columns,
        "row_count": len(rows),
        "rows": rows,
        **extra,
    }

    os.makedirs(out_dir, exist_ok=True)
    written = []
    if "json" in formats:
        written.append(generate.write_json(envelope, out_dir))
    if "csv" in formats:
        written.append(generate.write_csv(envelope, out_dir))
    if "xlsx" in formats:
        written.append(render.render_excel(envelope, os.path.join(out_dir, f"{name}.xlsx")))
    if "pdf" in formats:
        written.append(render.render_pdf(envelope, os.path.join(out_dir, f"{name}.pdf")))
    if verbose:
        print(f"  {envelope['title']} ({len(rows)} lines) -> "
              + ", ".join(os.path.basename(f) for f in written))
    return envelope, written


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a what-if scenario on the outlook.")
    parser.add_argument("--scenario", required=True, help="Scenario JSON file.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Source database.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output folder.")
    parser.add_argument("--format", nargs="+", default=["json", "xlsx", "pdf"],
                        choices=["json", "csv", "xlsx", "pdf"], help="Output format(s).")
    args = parser.parse_args(argv)
    try:
        generate_scenario(args.db, args.scenario, args.out, formats=tuple(args.format))
    except (ScenarioError, FileNotFoundError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
