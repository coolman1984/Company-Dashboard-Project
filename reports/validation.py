"""
validation.py - data-quality / import-validation report builder.

Produces a self-describing envelope that auditors can hand to stakeholders:
expected row counts vs. actual, nulls, duplicates, version coverage, and
source lineage.  No client data is exposed; it only summarises pl_detail.db.
"""
from __future__ import annotations

import sqlite3


def build_import_validation(conn: sqlite3.Connection):
    """Return (columns, rows, extra) for the import-validation report."""
    cursor = conn.cursor()

    # Total rows and years/versions present
    total_rows = cursor.execute("SELECT COUNT(*) FROM pl_detail").fetchone()[0]
    year_rows = cursor.execute(
        "SELECT year, COUNT(*) AS rows FROM pl_detail GROUP BY year ORDER BY year"
    ).fetchall()
    version_rows = cursor.execute(
        "SELECT version, COUNT(*) AS rows FROM pl_detail GROUP BY version ORDER BY version"
    ).fetchall()

    # Distinct dimensions
    regions = cursor.execute("SELECT COUNT(DISTINCT region_desc) FROM pl_detail").fetchone()[0]
    products = cursor.execute("SELECT COUNT(DISTINCT m_group_desc) FROM pl_detail").fetchone()[0]
    countries = cursor.execute("SELECT COUNT(DISTINCT country_name) FROM pl_detail").fetchone()[0]
    customers = cursor.execute("SELECT COUNT(DISTINCT customer_name) FROM pl_detail").fetchone()[0]

    # Duplicate-grain check: same year/version/period/region/m_group/country/customer
    duplicates = cursor.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT year, version, period, region_desc, m_group_desc, country_name, customer_name
          FROM pl_detail
          GROUP BY year, version, period, region_desc, m_group_desc, country_name, customer_name
          HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    # Most recent / oldest periods
    period_range = cursor.execute(
        "SELECT MIN(period), MAX(period) FROM pl_detail"
    ).fetchone()

    # Source lineage coverage. Older databases may not have the lineage tables,
    # so fail gracefully rather than breaking report generation.
    lineage_rows = source_files = import_runs = 0
    try:
        lineage_rows = cursor.execute("SELECT COUNT(*) FROM row_lineage").fetchone()[0]
        source_files = cursor.execute("SELECT COUNT(*) FROM source_file").fetchone()[0]
        import_runs = cursor.execute("SELECT COUNT(*) FROM import_run").fetchone()[0]
    except sqlite3.Error:
        lineage_rows = source_files = import_runs = 0
    lineage_pct = round((lineage_rows / total_rows * 100), 2) if total_rows else 0

    # Null / missing checks on the business-critical columns
    null_checks = cursor.execute(
        """
        SELECT
          SUM(CASE WHEN year         IS NULL THEN 1 ELSE 0 END) AS null_year,
          SUM(CASE WHEN version      IS NULL THEN 1 ELSE 0 END) AS null_version,
          SUM(CASE WHEN period       IS NULL THEN 1 ELSE 0 END) AS null_period,
          SUM(CASE WHEN region_desc  IS NULL THEN 1 ELSE 0 END) AS null_region,
          SUM(CASE WHEN m_group_desc IS NULL THEN 1 ELSE 0 END) AS null_product,
          SUM(CASE WHEN net_sales    IS NULL THEN 1 ELSE 0 END) AS null_net_sales,
          SUM(CASE WHEN cost_of_goods_sold IS NULL THEN 1 ELSE 0 END) AS null_cogs,
          SUM(CASE WHEN operating_profit IS NULL THEN 1 ELSE 0 END) AS null_op_profit
        FROM pl_detail
        """
    ).fetchone()

    # Build the rows
    columns = [
        "category",
        "item",
        "value",
        "status",
    ]
    rows = [
        {"category": "Summary", "item": "Total rows in ledger", "value": total_rows, "status": "OK"},
        {"category": "Summary", "item": "Distinct regions", "value": regions, "status": "OK"},
        {"category": "Summary", "item": "Distinct product groups", "value": products, "status": "OK"},
        {"category": "Summary", "item": "Distinct countries", "value": countries, "status": "OK"},
        {"category": "Summary", "item": "Distinct customers", "value": customers, "status": "OK"},
        {"category": "Summary", "item": "Duplicate grain combinations", "value": duplicates, "status": "WARN" if duplicates else "OK"},
        {"category": "Summary", "item": "Period range", "value": f"{period_range[0]:.3f} - {period_range[1]:.3f}", "status": "OK"},
        {"category": "Lineage", "item": "Rows with source lineage", "value": f"{lineage_rows} / {total_rows} ({lineage_pct:.2f}%)", "status": "OK" if lineage_rows == total_rows else "WARN"},
        {"category": "Lineage", "item": "Source files", "value": source_files, "status": "OK" if source_files else "WARN"},
        {"category": "Lineage", "item": "Import runs", "value": import_runs, "status": "OK" if import_runs else "WARN"},
    ]
    for year, cnt in year_rows:
        rows.append({"category": "By year", "item": f"Year {year}", "value": cnt, "status": "OK"})
    for version, cnt in version_rows:
        rows.append({"category": "By version", "item": f"Version {version}", "value": cnt, "status": "OK"})

    null_col_names = [
        ("null_year", "Year"),
        ("null_version", "Version"),
        ("null_period", "Period"),
        ("null_region", "Region"),
        ("null_product", "Product group"),
        ("null_net_sales", "Net sales"),
        ("null_cogs", "COGS"),
        ("null_op_profit", "Operating profit"),
    ]
    for idx, (db_key, label) in enumerate(null_col_names):
        cnt = null_checks[idx]
        rows.append({
            "category": "Null checks",
            "item": label,
            "value": cnt,
            "status": "OK" if cnt == 0 else "WARN",
        })

    extra = {
        "ledger_row_count": total_rows,
        "duplicate_grain_count": duplicates,
        "lineage_row_count": lineage_rows,
        "lineage_coverage_pct": lineage_pct,
        "source_file_count": source_files,
        "import_run_count": import_runs,
    }
    return columns, rows, extra
