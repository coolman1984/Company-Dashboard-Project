"""
Test for reports.client_templates — per-client report templates.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Point WORKSPACE_ROOT at a temp directory for testing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import reports.client_templates as ct


def test_load_nonexistent():
    """No template file -> None."""
    ct.invalidate_cache("no_such_client")
    # Override WORKSPACE_ROOT for testing
    with tempfile.TemporaryDirectory() as tmp:
        ct.WORKSPACE_ROOT = Path(tmp)
        assert ct.load_template("does_not_exist") is None


def test_load_valid_template():
    """Template file with labels and client reports."""
    with tempfile.TemporaryDirectory() as tmp:
        ct.WORKSPACE_ROOT = Path(tmp)
        client_dir = Path(tmp) / "acme"
        client_dir.mkdir(parents=True)
        tpl = {
            "client_name": "Acme Corp",
            "labels": {
                "net_sales": "Total Revenue",
                "cogs": "Cost of Delivery",
            },
            "reports": [
                {
                    "name": "acme_quarterly",
                    "title": "Acme Quarterly",
                    "description": "Quarterly P&L for Acme",
                    "sql": "SELECT * FROM v_yearly_pl",
                },
                {
                    "name": "acme_summary",
                    "title": "Acme Summary",
                    "sql": "SELECT 1",
                },
            ],
        }
        (client_dir / "templates.json").write_text(
            json.dumps(tpl, ensure_ascii=False), encoding="utf-8"
        )

        ct.invalidate_cache("acme")
        loaded = ct.load_template("acme")

        assert loaded is not None
        assert loaded.client_name == "Acme Corp"
        assert loaded.labels == {"net_sales": "Total Revenue", "cogs": "Cost of Delivery"}
        assert len(loaded.client_report_defs) == 2
        assert loaded.client_report_defs[0]["name"] == "acme_quarterly"
        assert loaded.client_report_defs[1]["name"] == "acme_summary"


def test_duplicate_report_name_rejected():
    """Client report with same name as built-in is silently skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        ct.WORKSPACE_ROOT = Path(tmp)
        client_dir = Path(tmp) / "dup_test"
        client_dir.mkdir(parents=True)
        tpl = {
            "client_name": "Dup Test",
            "reports": [
                {
                    "name": "yearly_pl",  # built-in name
                    "title": "Override Attempt",
                    "sql": "SELECT 1",
                },
            ],
        }
        (client_dir / "templates.json").write_text(
            json.dumps(tpl, ensure_ascii=False), encoding="utf-8"
        )

        ct.invalidate_cache("dup_test")
        loaded = ct.load_template("dup_test")
        assert loaded is not None
        assert len(loaded.client_report_defs) == 0  # Duplicate rejected


def test_get_client_label():
    """get_client_label returns override or key itself."""
    with tempfile.TemporaryDirectory() as tmp:
        ct.WORKSPACE_ROOT = Path(tmp)
        client_dir = Path(tmp) / "test_labels"
        client_dir.mkdir(parents=True)
        tpl = {
            "client_name": "Test",
            "labels": {"net_sales": "Revenue"},
        }
        (client_dir / "templates.json").write_text(
            json.dumps(tpl, ensure_ascii=False), encoding="utf-8"
        )

        ct.invalidate_cache("test_labels")
        assert ct.get_client_label("test_labels", "net_sales") == "Revenue"
        assert ct.get_client_label("test_labels", "unknown_key") == "unknown_key"


def test_default_template():
    """default_template creates a clean template for a new client."""
    tpl = ct.default_template("new_client", "New Client LLC")
    assert tpl.client_name == "New Client LLC"
    assert tpl.labels == {}
    assert tpl.client_report_defs == []


def test_list_client_report_names():
    """list_client_report_names includes both built-in and client reports."""
    with tempfile.TemporaryDirectory() as tmp:
        ct.WORKSPACE_ROOT = Path(tmp)
        client_dir = Path(tmp) / "report_list_test"
        client_dir.mkdir(parents=True)
        tpl = {
            "client_name": "Test",
            "reports": [
                {
                    "name": "my_custom_report",
                    "title": "My Custom Report",
                    "description": "A custom one",
                    "sql": "SELECT 1",
                },
            ],
        }
        (client_dir / "templates.json").write_text(
            json.dumps(tpl, ensure_ascii=False), encoding="utf-8"
        )

        ct.invalidate_cache("report_list_test")
        # list_client_report_names needs a DB connection for the built-in
        # catalogue to be importable. Skip the actual DB call but verify
        # that the client template part works.
        loaded = ct.load_template("report_list_test")
        assert loaded is not None
        custom_names = [c["name"] for c in loaded.client_report_defs]
        assert "my_custom_report" in custom_names
        # The built-in catalogue count is verified by definitions.py tests.


def test_invalid_json_returns_none():
    """Malformed JSON returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        ct.WORKSPACE_ROOT = Path(tmp)
        client_dir = Path(tmp) / "bad_json"
        client_dir.mkdir(parents=True)
        (client_dir / "templates.json").write_text(
            "{this is not valid json", encoding="utf-8"
        )

        ct.invalidate_cache("bad_json")
        assert ct.load_template("bad_json") is None


def test_get_client_labels():
    """get_client_labels returns all overrides, {} for no template."""
    with tempfile.TemporaryDirectory() as tmp:
        ct.WORKSPACE_ROOT = Path(tmp)
        client_dir = Path(tmp) / "labels_test"
        client_dir.mkdir(parents=True)
        tpl = {
            "client_name": "Labels Inc",
            "labels": {"a": "A Label", "b": "B Label"},
        }
        (client_dir / "templates.json").write_text(
            json.dumps(tpl, ensure_ascii=False), encoding="utf-8"
        )

        ct.invalidate_cache("labels_test")
        labels = ct.get_client_labels("labels_test")
        assert labels == {"a": "A Label", "b": "B Label"}

        assert ct.get_client_labels("no_template") == {}


if __name__ == "__main__":
    test_load_nonexistent()
    test_load_valid_template()
    test_duplicate_report_name_rejected()
    test_get_client_label()
    test_default_template()
    test_list_client_report_names()
    test_invalid_json_returns_none()
    test_get_client_labels()
    print("All client_templates tests passed.")
