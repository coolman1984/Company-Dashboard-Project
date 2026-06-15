"""
test_import_workspace.py — unit tests for the Phase 2 import workspace.

Run: python3 test_import_workspace.py
Exits 0 on success, 1 on any failure.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import import_workspace as iw


WORKSPACE_TMP = Path(tempfile.mkdtemp(prefix="cdash-ws-"))


def cleanup_workspace_root():
    """Wipe and recreate the workspace root before each test class."""
    if iw.WORKSPACE_ROOT.exists():
        shutil.rmtree(iw.WORKSPACE_ROOT)


class TestRunDirs(unittest.TestCase):
    def setUp(self):
        cleanup_workspace_root()

    def test_make_run_id_format(self):
        rid = iw.make_run_id()
        self.assertRegex(rid, r"^run-\d{8}-\d{6}$")

    def test_make_run_id_deterministic(self):
        from datetime import datetime
        stamp = datetime(2026, 6, 15, 13, 0, 0)
        self.assertEqual(iw.make_run_id(stamp), "run-20260615-130000")

    def test_client_workspace_path(self):
        p = iw.client_workspace("acme")
        self.assertEqual(p, iw.WORKSPACE_ROOT / "acme")

    def test_run_workspace_path(self):
        p = iw.run_workspace("acme", "run-x")
        self.assertEqual(p, iw.WORKSPACE_ROOT / "acme" / "runs" / "run-x")

    def test_ensure_run_dirs_creates_subdirs(self):
        run = iw.run_workspace("acme", "run-1")
        iw.ensure_run_dirs(run)
        self.assertTrue((run / "raw").is_dir())
        self.assertTrue((run / "logs").is_dir())
        self.assertTrue((run / "reports").is_dir())

    def test_invalid_client_id_rejected(self):
        with self.assertRaises(ValueError):
            iw.client_workspace("")
        with self.assertRaises(ValueError):
            iw.client_workspace(None)  # type: ignore[arg-type]

    def test_invalid_run_id_rejected(self):
        with self.assertRaises(ValueError):
            iw.run_workspace("acme", "")


class TestHistory(unittest.TestCase):
    def setUp(self):
        cleanup_workspace_root()

    def test_load_empty_history(self):
        data = iw.load_history("acme")
        self.assertEqual(data, {"client_id": "acme", "runs": []})

    def test_append_and_load(self):
        iw.append_history("acme", {"run_id": "r1", "status": "pending"})
        data = iw.load_history("acme")
        self.assertEqual(data["runs"][0]["run_id"], "r1")
        self.assertEqual(data["runs"][0]["status"], "pending")

    def test_prepend_newest_first(self):
        iw.append_history("acme", {"run_id": "r1", "status": "pending"})
        iw.append_history("acme", {"run_id": "r2", "status": "pending"})
        data = iw.load_history("acme")
        self.assertEqual([r["run_id"] for r in data["runs"]], ["r2", "r1"])

    def test_history_capped(self):
        for i in range(iw.HISTORY_MAX_ENTRIES + 10):
            iw.append_history("acme", {"run_id": f"r{i:03d}", "status": "pending"})
        data = iw.load_history("acme")
        self.assertEqual(len(data["runs"]), iw.HISTORY_MAX_ENTRIES)
        # Newest stays on top
        self.assertEqual(data["runs"][0]["run_id"], f"r{iw.HISTORY_MAX_ENTRIES + 9:03d}")

    def test_update_run_merges_fields(self):
        iw.append_history("acme", {"run_id": "r1", "status": "pending"})
        iw.update_run("acme", "r1", status="success", row_count=42)
        run = iw.load_history("acme")["runs"][0]
        self.assertEqual(run["status"], "success")
        self.assertEqual(run["row_count"], 42)
        self.assertEqual(run["run_id"], "r1")

    def test_update_run_missing_raises(self):
        iw.append_history("acme", {"run_id": "r1", "status": "pending"})
        with self.assertRaises(KeyError):
            iw.update_run("acme", "r2", status="success")

    def test_append_rejects_missing_run_id(self):
        with self.assertRaises(ValueError):
            iw.append_history("acme", {"status": "pending"})

    def test_append_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            iw.append_history("acme", "not a dict")  # type: ignore[arg-type]


class TestBackupAndPromote(unittest.TestCase):
    def setUp(self):
        cleanup_workspace_root()
        self.tmp_db = Path(tempfile.mkdtemp()) / "live.db"
        conn = sqlite3.connect(self.tmp_db)
        conn.execute("CREATE TABLE t (a TEXT)")
        conn.execute("INSERT INTO t VALUES ('before')")
        conn.commit()
        conn.close()

    def tearDown(self):
        if self.tmp_db.exists():
            self.tmp_db.unlink()

    def test_backup_creates_file(self):
        run = iw.run_workspace("acme", "run-1")
        iw.ensure_run_dirs(run)
        backup = iw.backup_database(self.tmp_db, run)
        self.assertTrue(os.path.exists(backup))
        # Contents match
        conn = sqlite3.connect(backup)
        row = conn.execute("SELECT a FROM t").fetchone()
        conn.close()
        self.assertEqual(row[0], "before")

    def test_backup_missing_source_returns_empty(self):
        run = iw.run_workspace("acme", "run-1")
        iw.ensure_run_dirs(run)
        result = iw.backup_database("/no/such/file.db", run)
        self.assertEqual(result, "")

    def test_promote_atomic_swap(self):
        staging = Path(tempfile.mkdtemp()) / "staging.db"
        conn = sqlite3.connect(staging)
        conn.execute("CREATE TABLE t (a TEXT)")
        conn.execute("INSERT INTO t VALUES ('after')")
        conn.commit()
        conn.close()
        iw.promote_database(staging, self.tmp_db)
        self.assertFalse(staging.exists())
        conn = sqlite3.connect(self.tmp_db)
        row = conn.execute("SELECT a FROM t").fetchone()
        conn.close()
        self.assertEqual(row[0], "after")

    def test_promote_missing_staging_raises(self):
        with self.assertRaises(FileNotFoundError):
            iw.promote_database("/no/such/staging.db", self.tmp_db)


class TestCopyRawInputs(unittest.TestCase):
    def setUp(self):
        cleanup_workspace_root()
        self.raw_dir = Path(tempfile.mkdtemp())
        for name in ("PL_2024.raw.json", "PL_2025.raw.json", "notes.raw.json"):
            (self.raw_dir / name).write_text('{"sheets": []}', encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.raw_dir, ignore_errors=True)

    def test_copy_matching_only(self):
        run = iw.run_workspace("acme", "run-1")
        iw.ensure_run_dirs(run)
        copied = iw.copy_raw_inputs(self.raw_dir, "*PL*.raw.json", run / "raw")
        self.assertEqual(set(copied), {"PL_2024.raw.json", "PL_2025.raw.json"})
        # Originals still on disk
        self.assertTrue((self.raw_dir / "PL_2024.raw.json").exists())


class TestLatestGoodRun(unittest.TestCase):
    def setUp(self):
        cleanup_workspace_root()

    def test_no_runs(self):
        self.assertIsNone(iw.latest_good_run("acme"))

    def test_picks_most_recent_success(self):
        iw.append_history("acme", {"run_id": "r1", "status": "failed"})
        iw.append_history("acme", {"run_id": "r2", "status": "success"})
        iw.append_history("acme", {"run_id": "r3", "status": "failed"})
        iw.append_history("acme", {"run_id": "r4", "status": "success"})
        run = iw.latest_good_run("acme")
        self.assertIsNotNone(run)
        self.assertEqual(run["run_id"], "r4")


class TestWriteValidation(unittest.TestCase):
    def setUp(self):
        cleanup_workspace_root()

    def test_write_validation_persists(self):
        run = iw.run_workspace("acme", "run-1")
        iw.ensure_run_dirs(run)
        path = iw.write_validation(run, {"status": "success", "rows": 100})
        self.assertTrue(os.path.exists(path))
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["rows"], 100)


def tearDownModule():
    if WORKSPACE_TMP.exists():
        shutil.rmtree(WORKSPACE_TMP, ignore_errors=True)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
