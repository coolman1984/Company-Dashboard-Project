"""
anomaly.py - the "passive guardian": deterministic anomaly detection over the
ledger so the system flags what changed instead of waiting to be asked.

Every anomaly is fully **source-traceable**: it carries the exact year,
dimension, label and metric it was computed from, so the UI can point a
challenged figure straight back at the database rows behind it. No statistics
black box, no network, no LLM — the rules are explicit and unit-tested, which is
what a finance audience needs ("why did you flag this?" must have a clear answer).

Detectors (all comparisons respect the project's outlook convention — the
current year is Actual P01-P05 + T06 P06 + T07 P07-P12; prior years are
full-year Actual):

  * first_negative_margin - a product group's operating profit turns negative
    for the first time after N positive years.
  * margin_erosion       - a product group's gross-margin % drops materially YoY.
  * customer_churn        - a consistently-buying customer collapses to ~0.
  * expense_spike         - a region's operating expense grows far faster than
    its revenue YoY.
  * period_spike          - a within-year month deviates sharply from the year's
    own average (z-score) for a monitored metric.

Usage:
    python3 -m reports.anomaly                 # human summary
    python3 -m reports.anomaly --json          # machine JSON (for the dashboard)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

from .outlook import PNUM, detect_years, _outlook_where

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")

# Tunable thresholds (explicit on purpose — a CFO can audit these).
MIN_REVENUE_FRACTION = 0.005   # ignore noise below 0.5% of total current revenue
MARGIN_EROSION_PP = 3.0        # gross-margin % drop that warrants a flag
MARGIN_EROSION_HIGH_PP = 5.0
CHURN_DROP_FRACTION = 0.10     # current < 10% of the customer's active prior average
EXPENSE_SPIKE_GROWTH_PCT = 15.0
EXPENSE_SPIKE_GAP_PCT = 10.0   # opex growth must outpace revenue growth by this much
PERIOD_SPIKE_Z = 2.5           # z-score beyond which a month is "unusual"


def _pct(part, whole):
    return (part / whole * 100.0) if whole else None


def _dim_year(conn, dimension, col, year, current):
    """{label: SUM(col)} for one dimension in one year, using the right coverage
    (outlook for the current year, full-year Actual for prior years)."""
    if year == current:
        wsql, wp = _outlook_where(conn, year)
    else:
        wsql, wp = "year = ? AND version = 'Actual'", (year,)
    sql = (f"SELECT COALESCE({dimension}, 'Unassigned') AS label, "
           f"COALESCE(SUM({col}), 0) AS v FROM pl_detail WHERE {wsql} GROUP BY {dimension}")
    return {row[0]: row[1] for row in conn.execute(sql, wp)}


def _period_series(conn, col, year, current):
    """[(period_number, value)] for a metric across a year's months."""
    if year == current:
        wsql, wp = _outlook_where(conn, year)
    else:
        wsql, wp = "year = ? AND version = 'Actual'", (year,)
    return conn.execute(
        f"SELECT {PNUM} AS p, COALESCE(SUM({col}), 0) AS v "
        f"FROM pl_detail WHERE {wsql} GROUP BY p ORDER BY p", wp).fetchall()


def _anomaly(type_, severity, metric, value, baseline, *, dimension=None,
             label=None, year=None, period=None, delta_pct=None, detail=None):
    delta = value - baseline
    return {
        "type": type_,
        "severity": severity,
        "dimension": dimension,
        "label": label,
        "metric": metric,
        "value": value,
        "baseline": baseline,
        "delta": delta,
        "delta_pct": delta_pct,
        "year": year,
        "period": period,
        "detail": detail or {},
        # explicit provenance so the UI can trace the number to its rows
        "source": {"year": year, "dimension": dimension, "label": label, "metric": metric},
    }


def detect_anomalies(conn):
    """Return a ranked list of anomaly dicts (most severe / largest first)."""
    current, prior = detect_years(conn)
    if current is None:
        return []
    years = [r[0] for r in conn.execute(
        "SELECT DISTINCT year FROM pl_detail WHERE year IS NOT NULL ORDER BY year")]

    total_rev = sum(_dim_year(conn, "m_group_desc", "net_sales", current, current).values())
    min_abs = abs(total_rev) * MIN_REVENUE_FRACTION
    anomalies = []

    # --- first-time negative operating profit (product groups) ----------------
    op_series = {y: _dim_year(conn, "m_group_desc", "operating_profit", y, current) for y in years}
    labels = set().union(*[set(s) for s in op_series.values()]) if op_series else set()
    for label in labels:
        cur = op_series[current].get(label, 0)
        if cur >= 0:
            continue
        priors = [op_series[y].get(label) for y in years if y != current and label in op_series[y]]
        if priors and all(p >= 0 for p in priors):
            anomalies.append(_anomaly(
                "first_negative_margin", "high", "operating_profit", cur, 0,
                dimension="m_group_desc", label=label, year=current,
                detail={"positive_years": len(priors)}))

    # --- gross-margin erosion (product groups) --------------------------------
    if prior is not None:
        ns_c = _dim_year(conn, "m_group_desc", "net_sales", current, current)
        gm_c = _dim_year(conn, "m_group_desc", "gross_margin", current, current)
        ns_p = _dim_year(conn, "m_group_desc", "net_sales", prior, current)
        gm_p = _dim_year(conn, "m_group_desc", "gross_margin", prior, current)
        for label, rev in ns_c.items():
            if rev <= min_abs or label not in ns_p or ns_p[label] <= 0:
                continue
            cur_pct = _pct(gm_c.get(label, 0), rev)
            pri_pct = _pct(gm_p.get(label, 0), ns_p[label])
            if cur_pct is None or pri_pct is None:
                continue
            drop = pri_pct - cur_pct
            if drop >= MARGIN_EROSION_PP:
                sev = "high" if drop >= MARGIN_EROSION_HIGH_PP else "medium"
                anomalies.append(_anomaly(
                    "margin_erosion", sev, "gross_margin_pct", cur_pct, pri_pct,
                    dimension="m_group_desc", label=label, year=current,
                    delta_pct=round(-drop, 2), detail={"drop_pp": round(drop, 2)}))

    # --- customer churn -------------------------------------------------------
    cust_series = {y: _dim_year(conn, "customer_name", "net_sales", y, current) for y in years}
    cust_labels = set().union(*[set(s) for s in cust_series.values()]) if cust_series else set()
    priors = [y for y in years if y != current]
    for label in cust_labels:
        active = [cust_series[y].get(label, 0) for y in priors if cust_series[y].get(label, 0) > 0]
        if len(active) < 2:
            continue
        avg = sum(active) / len(active)
        cur = cust_series[current].get(label, 0)
        if avg > min_abs and cur < CHURN_DROP_FRACTION * avg:
            anomalies.append(_anomaly(
                "customer_churn", "high", "net_sales", cur, avg,
                dimension="customer_name", label=label, year=current,
                delta_pct=round(_pct(cur - avg, abs(avg)) or 0, 2),
                detail={"active_prior_years": len(active)}))

    # --- expense spike vs revenue (regions) -----------------------------------
    if prior is not None:
        ox_c = _dim_year(conn, "region_desc", "operating_expense", current, current)
        ox_p = _dim_year(conn, "region_desc", "operating_expense", prior, current)
        rv_c = _dim_year(conn, "region_desc", "net_sales", current, current)
        rv_p = _dim_year(conn, "region_desc", "net_sales", prior, current)
        for label, ox in ox_c.items():
            if label not in ox_p or ox_p[label] <= 0:
                continue
            ox_growth = _pct(ox - ox_p[label], ox_p[label])
            rev_growth = _pct(rv_c.get(label, 0) - rv_p.get(label, 0), rv_p[label]) if rv_p.get(label, 0) > 0 else 0
            if ox_growth is not None and ox_growth >= EXPENSE_SPIKE_GROWTH_PCT \
                    and (ox_growth - (rev_growth or 0)) >= EXPENSE_SPIKE_GAP_PCT:
                sev = "high" if ox_growth >= 30 else "medium"
                anomalies.append(_anomaly(
                    "expense_spike", sev, "operating_expense", ox, ox_p[label],
                    dimension="region_desc", label=label, year=current,
                    delta_pct=round(ox_growth, 2),
                    detail={"revenue_growth_pct": round(rev_growth or 0, 2)}))

    # --- intra-year period spike (monitored metrics) --------------------------
    for metric in ("operating_expense", "net_sales"):
        series = _period_series(conn, metric, current, current)
        vals = [v for _p, v in series]
        n = len(vals)
        if n >= 4:
            mean = sum(vals) / n
            var = sum((v - mean) ** 2 for v in vals) / n
            std = var ** 0.5
            if std > 0:
                for pnum, v in series:
                    z = (v - mean) / std
                    if abs(z) >= PERIOD_SPIKE_Z and abs(v - mean) > min_abs:
                        sev = "high" if abs(z) >= 3.5 else "medium"
                        anomalies.append(_anomaly(
                            "period_spike", sev, metric, v, mean,
                            year=current, period=int(pnum),
                            delta_pct=round(_pct(v - mean, abs(mean)) or 0, 2),
                            detail={"z_score": round(z, 2)}))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    anomalies.sort(key=lambda a: (severity_rank.get(a["severity"], 9), -abs(a["delta"])))
    return anomalies


def build_report(db_path=DEFAULT_DB):
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it or load client data first.")
    conn = sqlite3.connect(db_path)
    try:
        current, prior = detect_years(conn)
        anomalies = detect_anomalies(conn)
    finally:
        conn.close()
    by_sev = {}
    for a in anomalies:
        by_sev[a["severity"]] = by_sev.get(a["severity"], 0) + 1
    return {
        "year": current,
        "prior_year": prior,
        "count": len(anomalies),
        "by_severity": by_sev,
        "anomalies": anomalies,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detect anomalies in the ledger.")
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
    print(f"FY{report['year']} guardian: {report['count']} anomaly(ies) "
          f"{report['by_severity']}")
    for a in report["anomalies"]:
        where = f"{a['dimension']}={a['label']}" if a["dimension"] else (
            f"P{a['period']:02d}" if a["period"] else "")
        print(f"  [{a['severity'].upper():6}] {a['type']:22} {where:28} "
              f"{a['metric']} value={a['value']:.0f} baseline={a['baseline']:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
