"""
decomposition.py - volume/price revenue decomposition.

Breaks revenue change between two years into:

  Price effect  = (current_price − base_price) × current_volume
  Volume effect = (current_volume − base_volume) × base_price

Where avg_price = net_sales / qty_net (net sales per unit sold).

A 10% revenue increase from price alone is very different from a 10% increase
from volume at lower price — this analysis shows which driver dominates and
whether margin dilution is hidden inside top-line growth.

Supports decomposition by any ledger dimension (region, product group, country,
customer) or at the group level. Uses only SQLite — no heavy analytics dependency.

Usage:
    python3 -m reports.decomposition --db pl_detail.db --json          # group level
    python3 -m reports.decomposition --db pl_detail.db --by region --json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import List, Tuple

from .outlook import detect_years

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")

DIMENSIONS = {
    "region":      ("region_desc",   "v_regional_pl"),
    "product":     ("m_group_desc",  "v_mgroup_pl"),
    "country":     ("country_name",  "v_country_pl"),
    "customer":    ("customer_name", "v_customer_pl"),
    "group":       (None,             "v_yearly_pl"),
}


def decompose(conn: sqlite3.Connection,
              base_year: int,
              compare_year: int,
              dimension_col: str | None = None,
              dimension_view: str = "v_yearly_pl",
              ) -> Tuple[List[str], List[dict], dict]:
    """
    Run the decomposition and return (columns, rows, extra).

    Parameters
    ----------
    conn : sqlite3.Connection
        Open read-only connection to the ledger.
    base_year : int
        The reference year (e.g. 2024).
    compare_year : int
        The comparison year (e.g. 2025).
    dimension_col : str or None
        The column to group by (e.g. 'region_desc'). None = group level.
    dimension_view : str
        The view that provides base data (used to detect available dimensions).

    Returns
    -------
    columns : list of str
    rows : list of dict
    extra : dict with summary totals
    """
    # Query per-group volume, net_sales, and avg_price for both years.
    group_by = f", {dimension_col}" if dimension_col else ""
    group_select = (f"{dimension_col} AS dimension_label" if dimension_col
                    else "'Group' AS dimension_label")
    # Use the ledger directly for group-level or the view for dimension-level
    from_table = "pl_detail" if not dimension_col else dimension_view

    sql = f"""
        WITH by_dim AS (
            SELECT
                {group_select},
                year,
                SUM(qty_net)    AS volume,
                SUM(net_sales)  AS net_sales,
                CASE WHEN SUM(qty_net) = 0 THEN 0
                     ELSE SUM(net_sales) / SUM(qty_net) END AS avg_price
            FROM pl_detail
            WHERE version = 'Actual'
              AND year IN ({base_year}, {compare_year})
              AND qty_net != 0
            GROUP BY {dimension_col or "'Group'"}, year
        ),
        base AS (SELECT * FROM by_dim WHERE year = {base_year}),
        curr AS (SELECT * FROM by_dim WHERE year = {compare_year})
        SELECT
            COALESCE(c.dimension_label, b.dimension_label)  AS dimension_label,
            ROUND(COALESCE(b.avg_price, 0), 4)               AS base_avg_price,
            ROUND(COALESCE(c.avg_price, 0), 4)               AS curr_avg_price,
            ROUND(COALESCE(b.volume, 0), 0)                  AS base_volume,
            ROUND(COALESCE(c.volume, 0), 0)                  AS curr_volume,
            ROUND(COALESCE(c.net_sales, 0) - COALESCE(b.net_sales, 0), 2)
                                                             AS total_change,
            ROUND((COALESCE(c.avg_price, 0) - COALESCE(b.avg_price, 0))
                  * COALESCE(c.volume, 0), 2)                AS price_effect,
            ROUND((COALESCE(c.volume, 0) - COALESCE(b.volume, 0))
                  * COALESCE(b.avg_price, 0), 2)             AS volume_effect
        FROM base b
        FULL OUTER JOIN curr c ON b.dimension_label = c.dimension_label
        WHERE ABS(COALESCE(c.net_sales, 0) - COALESCE(b.net_sales, 0)) > 0
        ORDER BY ABS(total_change) DESC
    """
    rows = conn.execute(sql).fetchall()
    columns = ["dimension_label", "base_avg_price", "curr_avg_price",
               "base_volume", "curr_volume", "total_change",
               "price_effect", "volume_effect"]

    result_rows = [dict(zip(columns, row)) for row in rows]

    # Summary
    total_change = sum(r["total_change"] for r in result_rows)
    price_effect = sum(r["price_effect"] for r in result_rows)
    volume_effect = sum(r["volume_effect"] for r in result_rows)

    extra = {
        "base_year": base_year,
        "compare_year": compare_year,
        "dimension": dimension_col or "group",
        "total_change": round(total_change, 2),
        "price_effect": round(price_effect, 2),
        "volume_effect": round(volume_effect, 2),
        "price_pct": round(price_effect / abs(total_change) * 100, 1)
                     if total_change else 0,
        "volume_pct": round(volume_effect / abs(total_change) * 100, 1)
                      if total_change else 0,
        "row_count": len(result_rows),
    }

    return columns, result_rows, extra


def auto_years(conn: sqlite3.Connection) -> Tuple[int, int]:
    """Pick the last two Actual years for decomposition."""
    years_row = conn.execute("""
        SELECT DISTINCT year FROM pl_detail
        WHERE version = 'Actual' ORDER BY year
    """).fetchall()
    years = [int(row[0]) for row in years_row]
    if len(years) < 2:
        # Try detect_years from outlook
        found = detect_years(conn)
        ys = sorted(found)
        if len(ys) >= 2:
            return ys[-2], ys[-1]
        # Fallback
        return 2024, 2025
    return years[-2], years[-1]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Volume/price revenue decomposition.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Source database.")
    parser.add_argument("--by", choices=list(DIMENSIONS.keys()),
                        default="group", help="Group-by dimension.")
    parser.add_argument("--base-year", type=int, default=None,
                        help="Base year (default: second-to-last Actual year).")
    parser.add_argument("--compare-year", type=int, default=None,
                        help="Comparison year (default: last Actual year).")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON.")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        dim_col, dim_view = DIMENSIONS[args.by]
        base_year = args.base_year
        compare_year = args.compare_year
        if base_year is None or compare_year is None:
            base_year, compare_year = auto_years(conn)

        columns, rows, extra = decompose(
            conn, base_year, compare_year,
            dimension_col=dim_col, dimension_view=dim_view,
        )

        if args.json:
            print(json.dumps({
                "columns": columns,
                "rows": rows,
                "extra": extra,
            }, ensure_ascii=False, indent=2, default=str))
            return 0

        print(f"\nVolume/Price Decomposition: {compare_year} vs {base_year}"
              f" (by {args.by})")
        print(f"  Total revenue change:  {extra['total_change']/1e6:+.1f}M")
        print(f"  Price effect:          {extra['price_effect']/1e6:+.1f}M"
              f"  ({extra['price_pct']:+.1f}%)")
        print(f"  Volume effect:         {extra['volume_effect']/1e6:+.1f}M"
              f"  ({extra['volume_pct']:+.1f}%)\n")
        if rows:
            print(f"  {'Dimension':<24} {'Change':>10} {'Price':>10} {'Volume':>10}")
            print(f"  {'─'*24:<24} {'─'*10:<10} {'─'*10:<10} {'─'*10:<10}")
            for r in rows[:15]:
                print(f"  {str(r['dimension_label'])[:24]:<24}"
                      f" {r['total_change']/1e6:>+9.1f}M"
                      f" {r['price_effect']/1e6:>+9.1f}M"
                      f" {r['volume_effect']/1e6:>+9.1f}M")
            if len(rows) > 15:
                print(f"  … and {len(rows) - 15} more rows")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
