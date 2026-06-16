"""
test_mcp.py — tests for the MCP server tools and JSON-RPC dispatch.

Runs on any platform (no MCP runtime needed): the tool logic and the
`handle_message` dispatch are pure. DB-backed tools use a throwaway database so
the real pl_detail.db is never touched; the wiki tools read the real
knowledge/ directory.

Run: python3 -m mcp_server.test_mcp
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest

import db_schema
from mcp_server import server, tools


class _TempDB:
    """Build a tiny valid pl_detail.db and point tools.DB_PATH at it."""

    def __enter__(self):
        self._dir = tempfile.mkdtemp()
        self._path = os.path.join(self._dir, "pl_detail.db")
        conn = sqlite3.connect(self._path)
        db_schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO pl_detail (year, version, period, region_desc, net_sales, "
            "cost_of_goods_sold, gross_margin) VALUES (?,?,?,?,?,?,?)",
            (2026, "Actual", 2026.001, "Asia Pacific", 100.0, 60.0, 40.0))
        conn.execute(
            "INSERT INTO pl_detail (year, version, period, region_desc, net_sales) "
            "VALUES (?,?,?,?,?)", (2025, "Actual", 2025.012, "Europe", 80.0))
        conn.execute(
            """
            INSERT INTO import_run (import_run_id, started_at, source, mapping_name, row_count, status)
            VALUES ('test-run', '2026-01-01T00:00:00Z', 'test_mcp.py', 'test', 2, 'success')
            """
        )
        cur = conn.execute(
            """
            INSERT INTO source_file (import_run_id, filename, relpath, extractor, document_type)
            VALUES ('test-run', 'test.raw.json', 'test.raw.json', 'test', 'spreadsheet')
            """
        )
        source_file_id = cur.lastrowid
        conn.executemany(
            """
            INSERT INTO row_lineage (ledger_rowid, import_run_id, source_file_id, sheet_name, source_row, raw_file, source_reference)
            VALUES (?, 'test-run', ?, 'Ledger', ?, 'test.raw.json', ?)
            """,
            [(1, source_file_id, 2, 'test.raw.json:Ledger:row:2'),
             (2, source_file_id, 3, 'test.raw.json:Ledger:row:3')]
        )
        conn.commit()
        conn.close()
        self._saved = tools.DB_PATH
        tools.DB_PATH = self._path
        return self

    def __exit__(self, *exc):
        tools.DB_PATH = self._saved


class TestDataTools(unittest.TestCase):
    def test_db_overview(self):
        with _TempDB():
            out = tools.db_overview()
        self.assertEqual(out["row_count"], 2)
        self.assertEqual(out["years"], [2025, 2026])
        self.assertEqual(out["versions"], ["Actual"])
        self.assertIn("net_sales", out["columns"])

    def test_run_select_ok(self):
        with _TempDB():
            out = tools.run_select({"sql": "SELECT year, net_sales FROM pl_detail ORDER BY year"})
        self.assertEqual(out["columns"], ["year", "net_sales"])
        self.assertEqual(out["row_count"], 2)

    def test_run_select_enforces_limit(self):
        with _TempDB():
            out = tools.run_select({"sql": "SELECT * FROM pl_detail", "limit": 1})
        self.assertEqual(out["row_count"], 1)

    def test_run_select_rejects_writes_and_pragma(self):
        with _TempDB():
            for bad in ("DELETE FROM pl_detail", "PRAGMA table_info(pl_detail)",
                        "SELECT 1; DROP TABLE pl_detail", "UPDATE pl_detail SET year=1"):
                with self.assertRaises(tools.ToolError):
                    tools.run_select({"sql": bad})

    def test_run_select_missing_db(self):
        saved = tools.DB_PATH
        tools.DB_PATH = "/no/such/pl_detail.db"
        try:
            with self.assertRaises(tools.ToolError):
                tools.run_select({"sql": "SELECT 1"})
        finally:
            tools.DB_PATH = saved

    def test_pl_summary(self):
        with _TempDB():
            out = tools.pl_summary()
        years = [r["year"] for r in out["years"]]
        self.assertEqual(years, [2025, 2026])

    def test_generate_report_returns_envelope(self):
        with _TempDB():
            out = tools.generate_report({"name": "import_validation"})
        self.assertEqual(out["report"], "import_validation")
        self.assertEqual(out["source"]["rows_in_ledger"], 2)
        self.assertIn("lineage_coverage_pct", out)
        self.assertEqual(out["lineage_coverage_pct"], 100.0)

    def test_generate_report_rejects_unknown(self):
        with _TempDB():
            with self.assertRaises(tools.ToolError):
                tools.generate_report({"name": "nope"})


class TestExtractionTool(unittest.TestCase):
    def test_availability_lists_extractors(self):
        out = tools.extractor_availability()
        names = [e["name"] for e in out["extractors"]]
        self.assertIn("excel-com", names)
        self.assertIn("csv-text", names)


class TestWikiTools(unittest.TestCase):
    def test_search_and_get_real_note(self):
        # knowledge/glossary.md ships in the repo.
        res = tools.wiki_search({"query": "glossary"})
        self.assertGreaterEqual(res["match_count"], 1)
        got = tools.wiki_get({"note": "glossary"})
        self.assertIn("content", got)
        self.assertTrue(got["content"])

    def test_get_rejects_path_traversal(self):
        with self.assertRaises(tools.ToolError):
            tools.wiki_get({"note": "../README"})

    def test_search_requires_query(self):
        with self.assertRaises(tools.ToolError):
            tools.wiki_search({"query": "   "})


class TestJsonRpcDispatch(unittest.TestCase):
    def test_initialize(self):
        resp = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "company-dashboard")
        self.assertEqual(resp["result"]["protocolVersion"], server.PROTOCOL_VERSION)
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_initialized_notification_returns_none(self):
        self.assertIsNone(server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list(self):
        resp = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listed = resp["result"]["tools"]
        self.assertEqual({t["name"] for t in listed}, set(tools.TOOLS_BY_NAME))
        for t in listed:
            self.assertIn("inputSchema", t)
            self.assertNotIn("handler", t)  # never leak the Python callable

    def test_tools_call_success(self):
        with _TempDB():
            resp = server.handle_message({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "db_overview", "arguments": {}}})
        result = resp["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertIn("row_count", result["content"][0]["text"])

    def test_tools_call_unknown_is_error(self):
        resp = server.handle_message({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "nope", "arguments": {}}})
        self.assertTrue(resp["result"]["isError"])

    def test_tools_call_tool_error_is_reported(self):
        resp = server.handle_message({
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "wiki_get", "arguments": {"note": "../README"}}})
        self.assertTrue(resp["result"]["isError"])

    def test_unknown_method_request_errors(self):
        resp = server.handle_message({"jsonrpc": "2.0", "id": 6, "method": "frobnicate"})
        self.assertEqual(resp["error"]["code"], server.METHOD_NOT_FOUND)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
