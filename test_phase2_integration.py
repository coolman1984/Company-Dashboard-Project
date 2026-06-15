"""
test_phase2_integration.py — end-to-end test for Phase 2 workspace integration.

Run: python3 test_phase2_integration.py
Exits 0 on success, 1 on failure.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import import_workspace as iw
import map_raw_to_db as m


# Clean the workspace root between tests.
def cleanup():
    if iw.WORKSPACE_ROOT.exists():
        shutil.rmtree(iw.WORKSPACE_ROOT)


def _write_capture(raw_dir, filename, sheet_name, header, rows):
    os.makedirs(raw_dir, exist_ok=True)
    envelope = {
        "schema_version": 1,
        "source": {"filename": filename, "relpath": filename},
        "extractor": "excel-openpyxl",
        "document_type": "spreadsheet",
        "content": {"sheets": [{
            "name": sheet_name,
            "n_rows": len(rows) + 1,
            "n_cols": len(header),
            "cells": [header] + rows,
        }]},
        "warnings": [],
    }
    with open(os.path.join(raw_dir, filename), "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, ensure_ascii=False)


HEADER = ["Year", "Version", "Period", "Region", "Net Sales", "COGS", "Gross Margin"]
ROWS = [
    [2025, "Actual", 1, "Africa", 100000, 60000, 40000],
    [2025, "Actual", 2, "Africa", 110000, 66000, 44000],
    [2025, "Actual", 3, "Africa", 120000, 72000, 48000],
]
MAPPING = {
    "source_glob": "*PL*.raw.json",
    "sheet": "Ledger",
    "header_row": 0,
    "skip_blank_rows": True,
    "columns": {
        "Year": "year",
        "Version": "version",
        "Period": "period",
        "Region": "region_desc",
        "Net Sales": "net_sales",
        "COGS": "cost_of_goods_sold",
        "Gross Margin": "gross_margin",
    },
}


class TestWorkspaceIntegration(unittest.TestCase):
    def setUp(self):
        cleanup()
        self.work = Path(tempfile.mkdtemp(prefix="cdash-p2-"))
        self.raw_dir = self.work / "raw"
        self.db_path = self.work / "pl_detail.db"
        _write_capture(self.raw_dir, "PL_2025.raw.json", "Ledger", HEADER, ROWS)
        self.mapping_path = self.work / "mapping.json"
        with open(self.mapping_path, "w", encoding="utf-8") as fh:
            json.dump(MAPPING, fh)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        cleanup()

    def test_load_with_client_id_creates_workspace(self):
        m.load(
            str(self.mapping_path),
            raw_dir=str(self.raw_dir),
            db_path=str(self.db_path),
            force=True,
            client_id="acme",
        )
        # Workspace created
        cw = iw.client_workspace("acme")
        self.assertTrue(cw.exists())
        # Run dir created
        runs = list((cw / "runs").iterdir())
        self.assertEqual(len(runs), 1)
        run = runs[0]
        # Subdirs present
        for sub in ("raw", "logs", "reports"):
            self.assertTrue((run / sub).is_dir(), f"missing {sub}/")
        # Raw capture was copied
        self.assertTrue((run / "raw" / "PL_2025.raw.json").exists())
        # validation.json exists
        self.assertTrue((run / "validation.json").exists())
        with open(run / "validation.json", encoding="utf-8") as fh:
            v = json.load(fh)
        self.assertEqual(v["status"], "success")
        self.assertEqual(v["row_count"], 3)
        # import_history.json exists and is correct
        history = iw.load_history("acme")
        self.assertEqual(len(history["runs"]), 1)
        self.assertEqual(history["runs"][0]["status"], "success")
        self.assertEqual(history["runs"][0]["row_count"], 3)
        # Live database is in place
        self.assertTrue(self.db_path.exists())

    def test_second_run_creates_backup(self):
        # First run — sets up the live DB.
        m.load(str(self.mapping_path), raw_dir=str(self.raw_dir),
               db_path=str(self.db_path), force=True, client_id="acme")
        # Second run on the same client — must produce a db-before.db backup.
        m.load(str(self.mapping_path), raw_dir=str(self.raw_dir),
               db_path=str(self.db_path), force=True, client_id="acme")
        cw = iw.client_workspace("acme")
        runs = sorted((cw / "runs").iterdir())
        self.assertEqual(len(runs), 2)
        # Newest run has a backup of the previous DB.
        self.assertTrue((runs[1] / "db-before.db").exists())
        history = iw.load_history("acme")
        self.assertEqual(len(history["runs"]), 2)
        self.assertEqual([r["status"] for r in history["runs"]], ["success", "success"])

    def test_no_client_id_keeps_legacy_behaviour(self):
        # No client_id → no workspace, no history. Backwards compatible.
        m.load(str(self.mapping_path), raw_dir=str(self.raw_dir),
               db_path=str(self.db_path), force=True, client_id=None)
        self.assertFalse(iw.WORKSPACE_ROOT.exists())
        self.assertTrue(self.db_path.exists())

    def test_rollback_preserves_backup(self):
        """rollback must copy the backup, not move it — so repeated rollbacks work."""
        # Create initial data
        m.load(str(self.mapping_path), raw_dir=str(self.raw_dir),
               db_path=str(self.db_path), force=True, client_id="test_rollback")
        # Create second run with backup
        m.load(str(self.mapping_path), raw_dir=str(self.raw_dir),
               db_path=str(self.db_path), force=True, client_id="test_rollback")
        
        cw = iw.client_workspace("test_rollback")
        runs = sorted((cw / "runs").iterdir())
        backup_path = runs[1] / "db-before.db"
        self.assertTrue(backup_path.exists())
        
        # Read backup content before rollback
        with open(backup_path, "rb") as f:
            backup_content_before = f.read()
        
        # Perform rollback
        from import_workspace_cli import cmd_rollback
        class Args:
            client = "test_rollback"
            db = str(self.db_path)
        
        rc = cmd_rollback(Args())
        self.assertEqual(rc, 0)
        
        # Verify backup still exists (critical!)
        self.assertTrue(backup_path.exists(), "backup must not be moved/deleted")
        with open(backup_path, "rb") as f:
            backup_content_after = f.read()
        self.assertEqual(backup_content_before, backup_content_after,
                        "backup content must not change")
        
        # Verify live DB now has backup content
        with open(self.db_path, "rb") as f:
            live_content = f.read()
        self.assertEqual(backup_content_before, live_content,
                        "live DB should match backup after rollback")


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
