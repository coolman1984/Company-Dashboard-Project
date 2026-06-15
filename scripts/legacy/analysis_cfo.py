"""
CFO / CEO Analysis Library  —  Company Dashboard
=================================================
Reads from pl_detail.db (SQLite) via DuckDB's SQLite scanner extension.
DuckDB handles the analytics with its vectorised execution engine.

Install once:
    pip install duckdb pandas

Usage (Claude Code / Codex / Cursor):
    python analysis_cfo.py                    # run all five analyses
    python analysis_cfo.py --analysis margin  # run one analysis
    python analysis_cfo.py --year 2025        # filter by year
    python analysis_cfo.py --region ASIA      # filter by region

Five CFO analyses implemented:
  1. margin     – Gross margin % trend and erosion risk by product group
  2. hhi        – Customer concentration (Herfindahl-Hirschman Index)
  3. forecast   – T06 / T07 forecast accuracy vs Actual (by period)
  4. leverage   – Operating leverage ratio by region
  5. decompose  – Revenue change decomposed into price effect vs volume effect
"""

import os
import sys
import json
import argparse
from datetime import datetime

try:
    import duckdb
    import pandas as pd
except ImportError:
    print("ERROR: Required packages missing. Run:  pip install duckdb pandas")
    sys.exit(1)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pl_detail.db")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfo_reports")

os.makedirs(OUT_DIR, exist_ok=True)

# ─── Connection ────────────────────────────────────────────────────────────────

def get_conn():
    """Open an in-memory DuckDB session with the SQLite database attached."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found: {DB_PATH}\nRun ingest_sheet1.py first.")
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL sqlite; LOAD sqlite;")
    conn.execute(f"ATTACH '{DB_PATH}' AS pl (TYPE SQLITE, READ_ONLY)")
    return conn


def q(conn, sql, params=None):
    """Execute SQL and return a pandas DataFrame."""
    if params:
        return conn.execute(sql, params).df()
    return conn.execute(sql).df()


def save(name, df, also_print=True):
    """Save DataFrame to CSV in cfo_reports/ and print a summary."""
    path = os.path.join(OUT_DIR, f"{name}.csv")
    df.to_csv(path, index=False)
    if also_print:
        print(f"\n{'─'*60}")
        print(df.to_string(index=False, max_rows=30))
    print(f"\n  → saved: {path}")
    return df


# ─── Analysis 1: Margin trend and erosion risk ─────────────────────────────────

def analysis_margin(conn, region=None):
    """
    Gross margin % by product group across all Actual years.
    Flags product groups where the 3-year regression slope is negative
    (margin is eroding) and shows the projected margin for next year.

    Why this matters: a product line that is profitable today but has a
    consistently declining margin % will turn loss-making. The CFO needs
    to see this before it happens, not after.
    """
    print("\n╔══ ANALYSIS 1: Gross Margin Trend & Erosion Risk ══╗")

    region_filter = "AND p.region_desc = ?" if region else ""
    params = [region] if region else None

    sql = f"""
        SELECT
            m_group_desc AS product_group,
            year,
            SUM(net_sales)     AS net_sales,
            SUM(gross_margin)  AS gross_margin,
            ROUND(SUM(gross_margin) / NULLIF(SUM(net_sales), 0) * 100, 2) AS gm_pct
        FROM pl.pl_detail p
        WHERE version = 'Actual'
          AND net_sales != 0
          {region_filter}
        GROUP BY m_group_desc, year
        ORDER BY m_group_desc, year
    """
    df = q(conn, sql, params)

    # For each product group, compute linear regression slope on gm_pct over years
    from numpy.polynomial import polynomial as P
    import numpy as np

    results = []
    for grp, sub in df.groupby("product_group"):
        if len(sub) < 2:
            continue
        years = sub["year"].values.astype(float)
        gm_pcts = sub["gm_pct"].values.astype(float)
        # Normalize years to 0-based for numerical stability
        yr_norm = years - years[0]
        try:
            coeffs = np.polyfit(yr_norm, gm_pcts, 1)  # slope, intercept
            slope = round(float(coeffs[0]), 3)
            next_yr = years[-1] + 1
            projected = round(float(np.polyval(coeffs, next_yr - years[0])), 2)
        except Exception:
            slope = None
            projected = None

        latest = sub.iloc[-1]
        results.append({
            "product_group":    grp,
            "latest_year":      int(latest["year"]),
            "latest_gm_pct":    float(latest["gm_pct"]),
            "annual_slope_pp":  slope,        # percentage-points per year change
            "projected_next_yr": projected,
            "status": (
                "🔴 ERODING"  if slope is not None and slope < -0.5 else
                "🟡 FLAT"     if slope is not None and abs(slope) <= 0.5 else
                "🟢 GROWING"
            ),
        })

    out = pd.DataFrame(results).sort_values("annual_slope_pp")
    save("margin_trend", out)
    return out


# ─── Analysis 2: Customer concentration HHI ────────────────────────────────────

def analysis_hhi(conn, year=None):
    """
    Herfindahl-Hirschman Index (HHI) of customer concentration.

    HHI = Σ (each customer's share of total net_sales, in %)²

    Interpretation:
      HHI < 1,500   → Low concentration (competitive, diversified)
      1,500–2,500   → Moderate concentration
      HHI > 2,500   → High concentration (risky — losing one customer hurts badly)

    Why this matters: a CFO preparing for a board meeting needs to answer
    "are we dangerously dependent on a handful of customers?"
    """
    print("\n╔══ ANALYSIS 2: Customer Concentration (HHI) ══╗")

    year_filter = "AND year = ?" if year else ""
    params = [year] if year else None

    sql = f"""
        WITH customer_sales AS (
            SELECT
                year,
                customer_name,
                SUM(net_sales) AS net_sales
            FROM pl.pl_detail
            WHERE version = 'Actual'
              AND net_sales > 0
              {year_filter}
            GROUP BY year, customer_name
        ),
        total_by_year AS (
            SELECT year, SUM(net_sales) AS total_sales
            FROM customer_sales
            GROUP BY year
        ),
        shares AS (
            SELECT
                cs.year,
                cs.customer_name,
                cs.net_sales,
                cs.net_sales / t.total_sales * 100 AS share_pct
            FROM customer_sales cs
            JOIN total_by_year t ON cs.year = t.year
        )
        SELECT
            year,
            ROUND(SUM(share_pct * share_pct), 1)                    AS hhi,
            COUNT(*)                                                 AS customer_count,
            ROUND(MAX(share_pct), 2)                                 AS top1_share_pct,
            ROUND(SUM(CASE WHEN rnk <= 5 THEN share_pct ELSE 0 END), 2) AS top5_share_pct,
            ROUND(SUM(CASE WHEN rnk <= 10 THEN share_pct ELSE 0 END), 2) AS top10_share_pct,
            CASE
                WHEN SUM(share_pct * share_pct) < 1500 THEN 'LOW  — diversified'
                WHEN SUM(share_pct * share_pct) < 2500 THEN 'MODERATE — watch top accounts'
                ELSE                                        'HIGH — concentration risk'
            END AS risk_level
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY year ORDER BY share_pct DESC) AS rnk
            FROM shares
        )
        GROUP BY year
        ORDER BY year
    """
    df = q(conn, sql, params)
    save("concentration_hhi", df)

    # Also show top-10 customers for the latest year
    latest_year = int(df["year"].max()) if not year else year
    top_sql = f"""
        WITH totals AS (
            SELECT SUM(net_sales) AS total FROM pl.pl_detail
            WHERE version='Actual' AND year={latest_year} AND net_sales > 0
        )
        SELECT
            customer_name,
            ROUND(SUM(net_sales) / 1e6, 2)                              AS net_sales_M,
            ROUND(SUM(net_sales) / (SELECT total FROM totals) * 100, 2) AS share_pct
        FROM pl.pl_detail
        WHERE version='Actual' AND year={latest_year} AND net_sales > 0
        GROUP BY customer_name
        ORDER BY net_sales DESC
        LIMIT 10
    """
    top10 = q(conn, top_sql)
    print(f"\nTop-10 customers in {latest_year}:")
    print(top10.to_string(index=False))
    top10.to_csv(os.path.join(OUT_DIR, f"top10_customers_{latest_year}.csv"), index=False)

    return df


# ─── Analysis 3: Forecast accuracy (T06 / T07 vs Actual) ──────────────────────

def analysis_forecast(conn):
    """
    Compare T06 and T07 forecast to Actual by period.

    For each period:
      - T06 covers period 6
      - T07 covers periods 7–12
    Compare against Actual values where both exist.

    Accuracy metric:
      error_pct = (forecast - actual) / |actual| × 100
      Positive = over-forecast (optimistic), Negative = under-forecast.

    Why this matters: if T06 consistently over-forecasts gross margin by 8%,
    the CEO knows to apply an 8% haircut when reading the 2026 outlook.
    """
    print("\n╔══ ANALYSIS 3: Forecast Accuracy (T06 / T07 vs Actual) ══╗")

    sql = """
        WITH period_sql AS (
            SELECT
                year,
                version,
                CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) AS period_num,
                SUM(net_sales)       AS net_sales,
                SUM(gross_margin)    AS gross_margin,
                SUM(operating_profit) AS operating_profit
            FROM pl.pl_detail
            WHERE year = 2026
              AND (
                (version = 'Actual' AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) BETWEEN 1 AND 12)
                OR (version = 'T06'  AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) = 6)
                OR (version = 'T07'  AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) BETWEEN 7 AND 12)
              )
            GROUP BY year, version, period_num
        ),
        actual AS (SELECT * FROM period_sql WHERE version = 'Actual'),
        forecast AS (SELECT * FROM period_sql WHERE version IN ('T06', 'T07'))
        SELECT
            f.period_num,
            f.version AS forecast_version,
            ROUND(a.net_sales / 1e6, 2)        AS actual_sales_M,
            ROUND(f.net_sales / 1e6, 2)        AS forecast_sales_M,
            ROUND((f.net_sales - a.net_sales) / NULLIF(ABS(a.net_sales), 0) * 100, 2) AS sales_error_pct,
            ROUND(a.gross_margin / NULLIF(a.net_sales, 0) * 100, 2)  AS actual_gm_pct,
            ROUND(f.gross_margin / NULLIF(f.net_sales, 0) * 100, 2)  AS forecast_gm_pct,
            ROUND(f.gross_margin / NULLIF(f.net_sales, 0) * 100
                - a.gross_margin / NULLIF(a.net_sales, 0) * 100, 2)  AS gm_pct_error_pp
        FROM forecast f
        JOIN actual a ON a.period_num = f.period_num
        ORDER BY f.period_num
    """
    df = q(conn, sql)

    if df.empty:
        print("  No overlapping Actual + Forecast periods found yet.")
        return df

    save("forecast_accuracy", df)

    avg_sales_err = df["sales_error_pct"].mean()
    avg_gm_err = df["gm_pct_error_pp"].mean()
    print(f"\n  Average sales error: {avg_sales_err:+.1f}%  ({'over' if avg_sales_err > 0 else 'under'}-forecast)")
    print(f"  Average GM error:    {avg_gm_err:+.2f} pp  ({'over' if avg_gm_err > 0 else 'under'}-forecast)")
    return df


# ─── Analysis 4: Operating leverage by region ──────────────────────────────────

def analysis_leverage(conn):
    """
    Operating leverage ratio = Operating profit / Net sales (EBIT margin %)
    and OPEX intensity = Operating expense / Gross margin.

    Tracks which regions show improving vs declining leverage year over year.

    Why this matters: resources (sales headcount, marketing budget) should flow
    to regions where each dollar of investment converts efficiently to profit.
    A region where operating leverage is deteriorating for 2+ years needs
    management attention before it becomes a loss centre.
    """
    print("\n╔══ ANALYSIS 4: Operating Leverage by Region ══╗")

    sql = """
        SELECT
            year,
            region_desc,
            ROUND(SUM(net_sales) / 1e6, 2)                                          AS net_sales_M,
            ROUND(SUM(gross_margin) / 1e6, 2)                                       AS gross_margin_M,
            ROUND(SUM(operating_expense) / 1e6, 2)                                  AS opex_M,
            ROUND(SUM(operating_profit) / 1e6, 2)                                   AS op_profit_M,
            ROUND(SUM(operating_profit) / NULLIF(SUM(net_sales), 0) * 100, 2)       AS ebit_margin_pct,
            ROUND(SUM(operating_expense) / NULLIF(SUM(gross_margin), 0) * 100, 2)   AS opex_intensity_pct
        FROM pl.pl_detail
        WHERE version = 'Actual'
          AND net_sales != 0
        GROUP BY year, region_desc
        ORDER BY region_desc, year
    """
    df = q(conn, sql)

    # Compute YoY change in EBIT margin per region
    df_sorted = df.sort_values(["region_desc", "year"])
    df_sorted["ebit_chg_pp"] = df_sorted.groupby("region_desc")["ebit_margin_pct"].diff().round(2)
    df_sorted["trend"] = df_sorted["ebit_chg_pp"].apply(
        lambda x: "↑ Improving" if x is not None and x > 0.5
                  else "↓ Declining" if x is not None and x < -0.5
                  else "→ Stable"
    )

    save("operating_leverage", df_sorted)
    return df_sorted


# ─── Analysis 5: Revenue decomposition (price vs volume) ───────────────────────

def analysis_decompose(conn, base_year=None, compare_year=None):
    """
    Decompose revenue change between two years into:
      Price effect  = (current_avg_price - prior_avg_price) × current_volume
      Volume effect = (current_volume - prior_volume) × prior_avg_price
      Mix effect    = residual (change in product composition)

    avg_price = net_sales / qty_net  (net sales per unit)

    Why this matters: a 10% revenue increase looks very different if it came
    entirely from price increases (sustainable, high quality) vs entirely from
    volume growth at lower price (may signal competitive pressure).
    """
    print("\n╔══ ANALYSIS 5: Revenue Decomposition (Price vs Volume) ══╗")

    sql_years = """
        SELECT DISTINCT year FROM pl.pl_detail
        WHERE version = 'Actual' ORDER BY year
    """
    years = q(conn, sql_years)["year"].tolist()

    if len(years) < 2:
        print("  Need at least 2 years of Actual data.")
        return pd.DataFrame()

    base_year    = base_year    or int(years[-2])
    compare_year = compare_year or int(years[-1])

    print(f"  Comparing {compare_year} vs {base_year}")

    sql = f"""
        WITH by_product AS (
            SELECT
                m_group_desc AS product_group,
                year,
                SUM(qty_net)    AS volume,
                SUM(net_sales)  AS net_sales,
                SUM(net_sales) / NULLIF(SUM(qty_net), 0) AS avg_price
            FROM pl.pl_detail
            WHERE version = 'Actual'
              AND year IN ({base_year}, {compare_year})
              AND qty_net != 0
            GROUP BY m_group_desc, year
        ),
        base AS (SELECT * FROM by_product WHERE year = {base_year}),
        curr AS (SELECT * FROM by_product WHERE year = {compare_year})
        SELECT
            COALESCE(c.product_group, b.product_group)  AS product_group,
            ROUND(COALESCE(b.avg_price, 0), 4)           AS base_avg_price,
            ROUND(COALESCE(c.avg_price, 0), 4)           AS curr_avg_price,
            ROUND(COALESCE(b.volume, 0), 0)              AS base_volume,
            ROUND(COALESCE(c.volume, 0), 0)              AS curr_volume,
            ROUND(COALESCE(c.net_sales, 0) - COALESCE(b.net_sales, 0), 2)  AS total_change,
            -- Price effect: (curr_price - base_price) × curr_volume
            ROUND((COALESCE(c.avg_price, 0) - COALESCE(b.avg_price, 0))
                  * COALESCE(c.volume, 0), 2)            AS price_effect,
            -- Volume effect: (curr_volume - base_volume) × base_price
            ROUND((COALESCE(c.volume, 0) - COALESCE(b.volume, 0))
                  * COALESCE(b.avg_price, 0), 2)          AS volume_effect
        FROM base b
        FULL OUTER JOIN curr c ON b.product_group = c.product_group
        ORDER BY ABS(COALESCE(c.net_sales, 0) - COALESCE(b.net_sales, 0)) DESC
        LIMIT 30
    """
    df = q(conn, sql)

    if not df.empty:
        total_change  = df["total_change"].sum()
        price_effect  = df["price_effect"].sum()
        volume_effect = df["volume_effect"].sum()
        print(f"\n  Total revenue change:  {total_change/1e6:+.1f}M")
        print(f"  Price effect:          {price_effect/1e6:+.1f}M  ({price_effect/abs(total_change)*100:+.1f}% of change)")
        print(f"  Volume effect:         {volume_effect/1e6:+.1f}M  ({volume_effect/abs(total_change)*100:+.1f}% of change)")

    save(f"decompose_{base_year}_{compare_year}", df)
    return df


# ─── Runner ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CFO analysis library for Company Dashboard")
    parser.add_argument("--analysis", choices=["margin", "hhi", "forecast", "leverage", "decompose", "all"],
                        default="all", help="Which analysis to run (default: all)")
    parser.add_argument("--year",   type=int, default=None, help="Filter by year (where supported)")
    parser.add_argument("--region", type=str, default=None, help="Filter by region_desc (where supported)")
    parser.add_argument("--base-year",    type=int, default=None, help="Base year for decompose analysis")
    parser.add_argument("--compare-year", type=int, default=None, help="Compare year for decompose analysis")
    args = parser.parse_args()

    print(f"\nCFO Analysis Library  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Database: {DB_PATH}")
    print(f"Reports:  {OUT_DIR}")

    conn = get_conn()

    try:
        run_all = args.analysis == "all"
        if run_all or args.analysis == "margin":
            analysis_margin(conn, region=args.region)
        if run_all or args.analysis == "hhi":
            analysis_hhi(conn, year=args.year)
        if run_all or args.analysis == "forecast":
            analysis_forecast(conn)
        if run_all or args.analysis == "leverage":
            analysis_leverage(conn)
        if run_all or args.analysis == "decompose":
            analysis_decompose(conn, base_year=args.base_year, compare_year=args.compare_year)
    finally:
        conn.close()

    print(f"\n✓ Done. All reports saved to {OUT_DIR}/")


if __name__ == "__main__":
    # numpy is optional — only needed for margin trend regression
    try:
        import numpy  # noqa: F401
    except ImportError:
        print("WARN: numpy not installed — margin trend slopes will be skipped.")
        print("      Install with:  pip install numpy")
    main()
