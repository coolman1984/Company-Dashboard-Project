"""
db_schema.py — the one place that turns schema.sql into a live database.

schema.sql is the single source of truth for the `pl_detail` ledger, its
indexes and its analytical views. Historically three different code paths
(seed_db.py, map_raw_to_db.py, ingest_sheet1.py) each built the schema their
own way, and the COM ingest had quietly drifted (different view columns). This
module centralises schema application so **every** path — synthetic seed, raw
mapper, and the Windows COM bulk ingest — produces a byte-for-byte identical
schema. A compatibility test (test_db_schema.py) guards against future drift.

No dependencies; pure stdlib; safe to import anywhere.
"""
from __future__ import annotations

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def read_schema(schema_path=SCHEMA_PATH):
    with open(schema_path, "r", encoding="utf-8") as handle:
        return handle.read()


def schema_columns(schema_path=SCHEMA_PATH):
    """Return [(name, type), ...] for pl_detail, in declared order."""
    sql = read_schema(schema_path)
    match = re.search(r"CREATE TABLE pl_detail\s*\((.*?)\)\s*;", sql, re.S | re.I)
    if not match:
        raise ValueError("Could not find CREATE TABLE pl_detail in schema.sql")
    columns = []
    for line in match.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        m = re.match(
            r'"?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"?\s+(?P<type>TEXT|INTEGER|REAL)',
            line, re.I,
        )
        if m:
            columns.append((m.group("name"), m.group("type").upper()))
    if not columns:
        raise ValueError("No columns parsed from schema.sql")
    return columns


def column_names(schema_path=SCHEMA_PATH):
    """Ordered list of pl_detail column names."""
    return [name for name, _ in schema_columns(schema_path)]


def column_types(schema_path=SCHEMA_PATH):
    """{name: TYPE} mapping for pl_detail columns."""
    return {name: typ for name, typ in schema_columns(schema_path)}


def split_statements(schema_path=SCHEMA_PATH):
    """Return (table_ddl, post_ddl).

    table_ddl  -> the DROP/CREATE TABLE statements (run first)
    post_ddl   -> indexes + views (run after a bulk load, per the perf plan)
    """
    raw = read_schema(schema_path)
    # Drop full-line comments so they never confuse statement splitting.
    cleaned = "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("--")
    )
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    table_ddl, post_ddl = [], []
    for stmt in statements:
        head = stmt.lstrip().upper()
        is_table = head.startswith("CREATE TABLE") or head.startswith("DROP TABLE")
        (table_ddl if is_table else post_ddl).append(stmt)
    return table_ddl, post_ddl


def apply_table(conn, schema_path=SCHEMA_PATH):
    """Create just the (empty) pl_detail table — for bulk-load-then-index flows."""
    table_ddl, _ = split_statements(schema_path)
    for stmt in table_ddl:
        conn.execute(stmt)
    conn.commit()


def apply_indexes_and_views(conn, schema_path=SCHEMA_PATH):
    """Create every index and view defined in schema.sql."""
    _, post_ddl = split_statements(schema_path)
    for stmt in post_ddl:
        conn.execute(stmt)
    conn.commit()


def apply_schema(conn, with_indexes_views=True, schema_path=SCHEMA_PATH):
    """Apply the full canonical schema to an open connection.

    Pass with_indexes_views=False to create only the table (then call
    apply_indexes_and_views after a bulk insert for best load performance).
    """
    apply_table(conn, schema_path)
    if with_indexes_views:
        apply_indexes_and_views(conn, schema_path)


# Names of the analytical views the dashboard/reports depend on. The
# compatibility test asserts these exist with stable output columns.
EXPECTED_VIEWS = (
    "v_yearly_pl", "v_regional_pl", "v_mgroup_pl",
    "v_country_pl", "v_customer_pl", "v_yoy_variance",
)
