"""
test_project_structure.py — guardrail that protects the project's organisation.

The root directory is intentionally kept small (see ARCHITECTURE.md). This test
fails if a stray script appears at the root or a layer package loses its README,
so the structure can't silently rot back into a 48-file root of spaghetti.

When you add a genuinely-canonical root file, add it to the allow-list below in
the same commit — that keeps the decision conscious and reviewed.

Run: python3 test_project_structure.py
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))

# Canonical root code/entry files. Anything else with these extensions at the
# root is a smell — it belongs in a layer package or under scripts/.
ALLOWED_ROOT_PY = {
    # data layer
    "db_schema.py", "seed_db.py",
    # extraction / load layer
    "map_raw_to_db.py", "ingest_sheet1.py",
    "import_workspace.py", "import_workspace_cli.py",
    # tests live next to the root modules they cover
    "test_db_schema.py", "test_map_raw_to_db.py",
    "test_import_workspace.py", "test_phase2_integration.py",
    "test_project_structure.py",
}
ALLOWED_ROOT_JS = {
    "server.js", "app.js", "i18n.js",   # presentation runtime
    "smoke_test.js",                      # server smoke test
    "chart.umd.min.js",                   # vendored asset (no CDN)
}

# Packages that must always carry a README explaining their purpose.
PACKAGES_NEEDING_README = ("extractor", "reports", "brain", "scripts/legacy", "docs")

# Docs that must exist at the root (the canonical set).
REQUIRED_ROOT_DOCS = (
    "README.md", "ARCHITECTURE.md", "ROADMAP.md", "AGENTS.md", "CLAUDE.md",
)


def _root_files(ext):
    return {f for f in os.listdir(ROOT)
            if f.endswith(ext) and os.path.isfile(os.path.join(ROOT, f))}


class TestRootIsClean(unittest.TestCase):
    def test_no_stray_root_python(self):
        stray = _root_files(".py") - ALLOWED_ROOT_PY
        self.assertEqual(stray, set(),
            f"Unexpected Python file(s) at the repo root: {sorted(stray)}. "
            "Put new code in its layer package or scripts/, or add it to "
            "ALLOWED_ROOT_PY in test_project_structure.py if it is truly canonical.")

    def test_no_stray_root_javascript(self):
        stray = _root_files(".js") - ALLOWED_ROOT_JS
        self.assertEqual(stray, set(),
            f"Unexpected JavaScript file(s) at the repo root: {sorted(stray)}. "
            "Put new code in its layer or scripts/, or update ALLOWED_ROOT_JS.")

    def test_allowlisted_files_actually_exist(self):
        # Keep the allow-list honest: every entry must still be present.
        for name in ALLOWED_ROOT_PY | ALLOWED_ROOT_JS:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, name)),
                            f"allow-listed root file is missing: {name}")


class TestPackagesDocumented(unittest.TestCase):
    def test_packages_have_readme(self):
        for pkg in PACKAGES_NEEDING_README:
            readme = os.path.join(ROOT, pkg, "README.md")
            self.assertTrue(os.path.isfile(readme), f"missing README: {pkg}/README.md")

    def test_required_root_docs_present(self):
        for doc in REQUIRED_ROOT_DOCS:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, doc)),
                            f"missing canonical root doc: {doc}")


class TestNoLegacyAtRoot(unittest.TestCase):
    def test_legacy_scripts_were_relocated(self):
        # These were moved to scripts/legacy/ — they must not reappear at root.
        for gone in ("precompute_data.py", "explore_sheet1.py", "extract_pl_data.py",
                     "create_indexes_views.py", "verify_db.py", "check_db.py"):
            self.assertFalse(os.path.isfile(os.path.join(ROOT, gone)),
                             f"legacy script is back at root: {gone} "
                             "(it belongs in scripts/legacy/)")


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
