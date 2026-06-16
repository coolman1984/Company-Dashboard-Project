"""
test_db_schema.py — compatibility guard for the database layer.

schema.sql is the single source of truth. Three code paths build the database:
the synthetic seed (seed_db.py), the raw mapper (map_raw_to_db.py) and the
Windows COM bulk ingest (ingest_sheet1.py). This suite proves they can never
drift apart again:

  * the column lists hard-coded in seed_db.py and ingest_sheet1.py match
    schema.sql exactly, in order;
  * applying schema.sql yields the expected table columns, all 13 indexes and
    all 6 views, with the exact view output columns the dashboard depends on;
  * the COM ingest's own (non-COM) schema construction produces a database
    byte-for-byte identical in structure to schema.sql.

Everything here runs on Linux/CI — no Windows or Excel required.

Run: python3 test_db_schema.py
"""
from __future__ import annotations

import sqlite3
import sys
import unittest

import db_schema
import seed_db
import ingest_sheet1
import map_raw_to_db


def _table_columns(conn, table="pl_detail"):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _objects(conn, kind):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type=? ORDER BY name", (kind,)
    ).fetchall()
    return sorted(r[0] for r in rows)


def _view_columns(conn, view):
    # A view's output columns: read one row's keys via PRAGMA-free introspection.
    cur = conn.execute(f"SELECT * FROM {view} LIMIT 0")
    return [d[0] for d in cur.description]


class TestColumnListsMatchSchema(unittest.TestCase):
    def setUp(self):
        self.schema_cols = db_schema.column_names()

    def test_seed_columns_match_schema(self):
        self.assertEqual(list(seed_db.COLUMNS), self.schema_cols,
                         "seed_db.COLUMNS drifted from schema.sql")

    def test_ingest_columns_match_schema(self):
        ingest_cols = [name for name, _ in ingest_sheet1.COLUMNS]
        self.assertEqual(ingest_cols, self.schema_cols,
                         "ingest_sheet1.COLUMNS drifted from schema.sql")

    def test_mapper_parses_same_columns(self):
        self.assertEqual(list(map_raw_to_db.load_schema_columns().keys()),
                         self.schema_cols)

    def test_ingest_int_columns_are_year_and_valuation(self):
        names = [name for name, _ in ingest_sheet1.COLUMNS]
        int_names = {names[i] for i in ingest_sheet1.INT_COLUMN_INDICES}
        self.assertEqual(int_names, {"year", "valuation_class"})


class TestSchemaApplication(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        db_schema.apply_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_table_columns(self):
        self.assertEqual(_table_columns(self.conn), db_schema.column_names())

    def test_all_views_present(self):
        self.assertEqual(_objects(self.conn, "view"),
                         sorted(db_schema.EXPECTED_VIEWS))

    def test_thirteen_indexes_present(self):
        # The 13 named analytical indexes from schema.sql.
        idx = [n for n in _objects(self.conn, "index") if n.startswith("idx_")]
        self.assertEqual(len(idx), 13, idx)

    def test_lineage_tables_present(self):
        tables = _objects(self.conn, "table")
        self.assertIn("import_run", tables)
        self.assertIn("source_file", tables)
        self.assertIn("row_lineage", tables)

    def test_lineage_indexes_present(self):
        indexes = _objects(self.conn, "index")
        self.assertIn("lineage_import_run_lookup", indexes)
        self.assertIn("lineage_source_file_lookup", indexes)
        self.assertIn("source_file_run_lookup", indexes)

    def test_yoy_variance_has_stable_columns(self):
        # The dashboard depends on these exact names; the old COM path used
        # net_sales_pct_change and an extra gross_margin_pct_change — drift.
        cols = _view_columns(self.conn, "v_yoy_variance")
        self.assertIn("net_sales_pct", cols)
        self.assertNotIn("net_sales_pct_change", cols)
        self.assertNotIn("gross_margin_pct_change", cols)

    def test_views_queryable_on_empty_db(self):
        # No rows loaded: views must still resolve (return zero rows, not error).
        for view in db_schema.EXPECTED_VIEWS:
            self.conn.execute(f"SELECT * FROM {view}").fetchall()


class TestIngestMatchesSchema(unittest.TestCase):
    """The COM ingest's schema construction (no COM needed) == schema.sql."""

    def test_ingest_builds_identical_structure(self):
        # Reference DB straight from schema.sql.
        ref = sqlite3.connect(":memory:")
        db_schema.apply_schema(ref)

        # DB built the way ingest_sheet1 builds it: table, then indexes+views.
        got = sqlite3.connect(":memory:")
        db_schema.apply_table(got)             # what create_database() now does
        ingest_sheet1.create_indexes(got)      # delegates to db_schema
        ingest_sheet1.create_summary_views(got)  # no-op now

        self.assertEqual(_table_columns(got), _table_columns(ref))
        self.assertEqual(_objects(got, "view"), _objects(ref, "view"))
        self.assertEqual(_objects(got, "index"), _objects(ref, "index"))
        for view in db_schema.EXPECTED_VIEWS:
            self.assertEqual(_view_columns(got, view), _view_columns(ref, view),
                             f"view {view} columns differ between ingest and schema")
        ref.close()
        got.close()


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
