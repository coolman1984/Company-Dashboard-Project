"""
data_notes.py - generate knowledge notes FROM the database.

This is what makes the wiki a "second brain connected to the data": for each
region it writes a Markdown note carrying the latest figures in frontmatter and
linking to the glossary and index, so curated knowledge and live numbers live in
the same linked space. Generated notes go under knowledge/data/ and are
git-ignored (they can contain real client figures).
"""
from __future__ import annotations

import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")
DEFAULT_OUT = os.path.join(BASE_DIR, "knowledge", "data")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "item"


def generate_region_notes(db_path=DEFAULT_DB, out_dir=DEFAULT_OUT, verbose=True):
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it or load client data first.")
    conn = sqlite3.connect(db_path)
    try:
        year = conn.execute("SELECT MAX(year) FROM pl_detail").fetchone()[0]
        rows = conn.execute(
            "SELECT region_desc, COALESCE(SUM(net_sales),0), COALESCE(SUM(gross_margin),0) "
            "FROM pl_detail WHERE version='Actual' AND year=? AND region_desc IS NOT NULL "
            "GROUP BY region_desc ORDER BY SUM(net_sales) DESC", (year,)).fetchall()
    finally:
        conn.close()

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for region, net_sales, gross_margin in rows:
        gm_pct = round(gross_margin / net_sales * 100, 1) if net_sales else 0
        note = (
            f"---\n"
            f"title: {region}\n"
            f"tags: [region, data]\n"
            f"year: {year}\n"
            f"net_sales: {net_sales:.0f}\n"
            f"gross_margin: {gross_margin:.0f}\n"
            f"---\n\n"
            f"# {region}\n\n"
            f"Auto-generated from the ledger for FY{year} (Actual). #region #data\n\n"
            f"- **Net sales:** {net_sales:,.0f}\n"
            f"- **Gross margin:** {gross_margin:,.0f} ({gm_pct}%)\n\n"
            f"See [[glossary]] for definitions and [[index]] for the map. "
            f"Regional detail also appears in the [[reports]].\n"
        )
        path = os.path.join(out_dir, f"region-{_slug(region)}.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(note)
        written.append(path)
        if verbose:
            print(f"  region note: {os.path.basename(path)}")
    return written
