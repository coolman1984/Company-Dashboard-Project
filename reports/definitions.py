"""
definitions.py - the catalogue of reports the engine can generate.

Each report is a named, documented SQL query against pl_detail.db. Most read the
canonical Actual-only views defined in schema.sql, so report figures tie out with
the dashboard by construction. To add a report, append a Report here - no other
code changes needed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Report:
    name: str          # file-safe identifier
    title: str         # human title
    description: str
    sql: str


REPORTS = [
    Report(
        name="yearly_pl",
        title="Yearly P&L Summary",
        description="Group-wide profit & loss by fiscal year (Actual).",
        sql="SELECT * FROM v_yearly_pl ORDER BY year",
    ),
    Report(
        name="regional_pl",
        title="Regional P&L",
        description="Profit & loss by region and year (Actual).",
        sql="SELECT * FROM v_regional_pl ORDER BY year, net_sales DESC",
    ),
    Report(
        name="product_group_pl",
        title="Product Group P&L",
        description="Profit & loss by product group and year (Actual).",
        sql="SELECT * FROM v_mgroup_pl ORDER BY year, net_sales DESC",
    ),
    Report(
        name="country_pl",
        title="Country P&L",
        description="Profit & loss by country and year (Actual).",
        sql="SELECT * FROM v_country_pl ORDER BY year, net_sales DESC",
    ),
    Report(
        name="customer_pl",
        title="Customer P&L",
        description="Profit & loss by customer and year (Actual).",
        sql="SELECT * FROM v_customer_pl ORDER BY year, net_sales DESC",
    ),
    Report(
        name="yoy_variance",
        title="Year-over-Year Variance",
        description="Year-on-year change in key P&L lines (Actual).",
        sql="SELECT * FROM v_yoy_variance ORDER BY year",
    ),
]

REPORTS_BY_NAME = {report.name: report for report in REPORTS}
