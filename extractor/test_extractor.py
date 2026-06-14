"""
Self-contained test for the extraction engine (no pytest required).

Exercises the cross-platform path end to end: build a messy .xlsx and a .docx in
a temp folder, run the orchestrator, and assert that faithful raw JSON and a
manifest are produced, that re-runs skip unchanged files, and that an
unsupported file is reported rather than crashing the run.

Run:  python3 -m extractor.test_extractor
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

from . import manifest, registry
from .cli import run


def _make_samples(intake_dir):
    os.makedirs(intake_dir, exist_ok=True)

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "P&L"
    ws.append(["Region", "Net Sales"])
    ws.append(["Africa", 1250000])
    ws.append([None, None])          # messy blank row must be preserved
    ws.append(["Europe", 980000])
    wb.save(os.path.join(intake_dir, "pl.xlsx"))

    import docx
    d = docx.Document()
    d.add_heading("Commentary", level=1)
    d.add_paragraph("Revenue grew.")
    d.save(os.path.join(intake_dir, "notes.docx"))

    # An unsupported file type to prove graceful skipping.
    with open(os.path.join(intake_dir, "random.xyz"), "w", encoding="utf-8") as fh:
        fh.write("not a known format")


def main():
    # Skip cleanly if the cross-platform libraries are unavailable.
    for module in ("openpyxl", "docx"):
        try:
            __import__(module)
        except Exception:  # noqa: BLE001
            print(f"SKIP: {module} not installed; extractor test not run.")
            return 0

    with tempfile.TemporaryDirectory() as tmp:
        intake = os.path.join(tmp, "intake")
        out = os.path.join(tmp, "raw")
        _make_samples(intake)

        summary = run(intake, out, force=False)
        assert summary["captured"] == 2, summary
        assert summary["unsupported"] == 1, summary
        assert summary["errors"] == 0, summary

        raw_files = [f for f in os.listdir(out) if f.endswith(".raw.json")]
        assert len(raw_files) == 2, raw_files

        excel_raw = next(f for f in raw_files if "pl.xlsx" in f)
        with open(os.path.join(out, excel_raw), encoding="utf-8") as fh:
            envelope = json.load(fh)
        assert envelope["document_type"] == "spreadsheet"
        assert envelope["source"]["sha256"]
        sheet = envelope["content"]["sheets"][0]
        assert sheet["cells"][1] == ["Africa", 1250000], sheet["cells"][1]
        assert sheet["n_rows"] == 4, "blank row should be preserved"

        # Manifest recorded the two successes.
        seen = manifest.load_seen_hashes(out)
        assert len(seen) == 2, seen

        # Re-run: nothing new captured (dedup by fingerprint).
        again = run(intake, out, force=False)
        assert again["captured"] == 0, again
        assert again["skipped_unchanged"] == 2, again

    # Availability listing must never raise, even with broken optional libs.
    rows = registry.describe_availability()
    assert any(r["name"] == "excel-com" for r in rows)

    print("Extractor tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
