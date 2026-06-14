"""
outlook.py - computed (forecast) reports for the reports engine.

Unlike the view-backed reports, these stitch the project's version/period
coverage convention into a forward-looking full-year picture, mirroring the
dashboard's executive outlook:

  the outlook (forecast) year = Actual P01-P05 + T06 P06 + T07 P07-P12

so realised months and forecast months combine into one full-year number, which
is then compared with the prior year's actuals. The outlook year is taken as the
latest year present; if that year has no forecast (T06/T07) rows it is treated as
a closed year (full-year Actual).

Each builder returns (columns, rows, extra), where `extra` carries report
metadata such as the basis (which years are being compared).
"""
from __future__ import annotations

# period REAL = year + period_number/1000  ->  recover the 1..12 period number.
PNUM = "CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER)"

# (display label, ledger column) for the P&L lines, top to bottom.
PL_LINES = [
    ("Net Sales", "net_sales"),
    ("COGS", "cost_of_goods_sold"),
    ("Gross Margin", "gross_margin"),
    ("Operating Expense", "operating_expense"),
    ("Operating Profit", "operating_profit"),
    ("Profit Before Tax", "profit_before_tax"),
    ("Corporate Tax", "corporate_tax"),
    ("Net Income", "net_income"),
]


def detect_years(conn):
    """(outlook_year, prior_year) — the latest year and the one before it."""
    row = conn.execute("SELECT MAX(year) FROM pl_detail WHERE year IS NOT NULL").fetchone()
    current = row[0]
    return current, (current - 1 if current is not None else None)


def _has_forecast(conn, year):
    n = conn.execute(
        "SELECT COUNT(*) FROM pl_detail WHERE year = ? AND version IN ('T06','T07')",
        (year,)).fetchone()[0]
    return n > 0


def _outlook_where(conn, year):
    """WHERE clause + params for a year's outlook coverage."""
    if _has_forecast(conn, year):
        sql = (f"year = ? AND ("
               f"  (version = 'Actual' AND {PNUM} BETWEEN 1 AND 5)"
               f"  OR (version = 'T06' AND {PNUM} = 6)"
               f"  OR (version = 'T07' AND {PNUM} BETWEEN 7 AND 12))")
    else:
        sql = "year = ? AND version = 'Actual'"
    return sql, (year,)


def _sum_lines(conn, where_sql, params):
    cols = ", ".join(f"COALESCE(SUM({c}), 0) AS {c}" for _, c in PL_LINES)
    row = conn.execute(f"SELECT {cols} FROM pl_detail WHERE {where_sql}", params).fetchone()
    return dict(zip([c for _, c in PL_LINES], row)) if row else {}


def build_outlook_pl(conn):
    """Full-year outlook vs prior-year actual, line by line, with variance."""
    columns = ["line_item", "outlook", "prior_year", "variance", "variance_pct"]
    current, prior = detect_years(conn)
    if current is None:
        return columns, [], {"basis": "no data"}

    out_where, out_params = _outlook_where(conn, current)
    outlook = _sum_lines(conn, out_where, out_params)
    prior_vals = _sum_lines(conn, "year = ? AND version = 'Actual'", (prior,))

    rows = []
    for label, col in PL_LINES:
        o = outlook.get(col, 0) or 0
        p = prior_vals.get(col, 0) or 0
        variance = o - p
        pct = round(variance / abs(p) * 100, 2) if p else None
        rows.append({"line_item": label, "outlook": o, "prior_year": p,
                     "variance": variance, "variance_pct": pct})
    return columns, rows, {"basis": f"FY{current} full-year outlook vs FY{prior} actual"}


def build_outlook_monthly(conn):
    """Month-by-month net sales and gross margin, flagged actual vs outlook."""
    columns = ["period_number", "period_label", "status", "net_sales", "gross_margin"]
    current, _prior = detect_years(conn)
    if current is None:
        return columns, [], {"basis": "no data"}

    where_sql, params = _outlook_where(conn, current)
    raw = conn.execute(
        f"SELECT {PNUM} AS period_number, version, "
        f"       COALESCE(SUM(net_sales), 0) AS net_sales, "
        f"       COALESCE(SUM(gross_margin), 0) AS gross_margin "
        f"FROM pl_detail WHERE {where_sql} "
        f"GROUP BY period_number, version ORDER BY period_number", params).fetchall()

    rows = []
    for period_number, version, net_sales, gross_margin in raw:
        rows.append({
            "period_number": period_number,
            "period_label": f"P{int(period_number):02d}",
            "status": "actual" if version == "Actual" else "outlook",
            "net_sales": net_sales,
            "gross_margin": gross_margin,
        })
    return columns, rows, {"basis": f"FY{current} monthly progression"}
