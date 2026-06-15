"""
excel_com.py - Windows Excel COM extractor (the primary "full control" path).

Drives Microsoft Excel directly via COM automation (win32com). This is the
preferred extractor on a Windows machine that has Excel installed because it:
  * opens ANY format Excel itself can open, including binary .xlsb workbooks
    that pure-Python libraries cannot read;
  * sees exactly what a human sees (evaluated formulas, the real used range);
  * gives full control over how the workbook is opened and read.

It produces the SAME raw-document envelope as excel_openpyxl.py, so the two are
interchangeable downstream.

NOTE: COM is Windows-only and cannot run on Linux/CI. The engine detects this
via is_available() and falls back to the openpyxl extractor automatically. All
the dangerous COM choreography (dialog-free session, no-hang open, guaranteed
cleanup, value cleaning) lives in com_utils.py and is unit-tested via mocks.
"""
from __future__ import annotations

import os
import sys

from . import com_utils
from .base import Extractor, optional_import

CHUNK_ROWS = 5000              # Bulk-read this many rows per COM call.
LARGE_FILE_MB = 200            # Warn (don't fail) above this size.


class ExcelComExtractor(Extractor):
    name = "excel-com"
    document_type = "spreadsheet"
    extensions = (".xlsx", ".xlsm", ".xlsb", ".xls")

    def is_available(self):
        if not sys.platform.startswith("win"):
            return False, "Excel COM requires Windows"
        if optional_import("win32com") is None:
            return False, "pywin32 is not installed (pip install pywin32)"
        return True, "ok"

    def extract_content(self, path: str):
        warnings = []

        if not os.path.exists(path):
            raise FileNotFoundError(f"file not found: {path}")
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb > LARGE_FILE_MB:
            warnings.append(
                f"File is very large ({size_mb:.1f} MB). COM extraction may be "
                "slow; consider the production ingest path."
            )

        sheets = []
        # excel_session guarantees Excel is quit and COM uninitialised even if
        # anything below raises — no orphaned EXCEL.EXE.
        with com_utils.excel_session() as excel:
            workbook = com_utils.open_workbook(excel, path, read_only=True)
            try:
                for sheet in workbook.Sheets:
                    # Isolate each sheet: one unreadable sheet (e.g. a chart
                    # sheet with no UsedRange) must not abort the whole file.
                    try:
                        sheets.append(self._read_sheet(sheet, warnings))
                    except Exception as exc:  # noqa: BLE001
                        warnings.append(
                            f"Sheet '{_safe_name(sheet)}': could not be read "
                            f"({exc}). Skipped."
                        )
            finally:
                try:
                    workbook.Close(SaveChanges=False)
                except Exception:  # noqa: BLE001
                    pass

        if not sheets:
            warnings.append("Workbook contained no readable sheets.")
        return {"sheets": sheets}, warnings

    def _read_sheet(self, sheet, warnings):
        used = sheet.UsedRange
        n_rows = int(used.Rows.Count)
        n_cols = int(used.Columns.Count)
        first_row = int(used.Row)
        first_col = int(used.Column)
        sheet_name = str(sheet.Name)

        rows = []
        error_cells = 0
        partial = False
        for top, bottom in com_utils.chunk_bounds(n_rows, CHUNK_ROWS, start_row=first_row):
            try:
                block = sheet.Range(
                    sheet.Cells(top, first_col),
                    sheet.Cells(bottom, first_col + n_cols - 1),
                ).Value
            except Exception as exc:  # noqa: BLE001 — keep the rows read so far
                warnings.append(
                    f"Sheet '{sheet_name}': read stopped near row {top} ({exc}). "
                    "Partial extraction."
                )
                partial = True
                break
            for com_row in com_utils.normalize_block(block):
                cleaned = []
                for value in com_row:
                    clean_val, had_error = com_utils.clean_com_value(value)
                    cleaned.append(clean_val)
                    if had_error:
                        error_cells += 1
                rows.append(cleaned)

        # Drop trailing fully-empty rows for a tight envelope.
        while rows and not any(cell not in (None, "") for cell in rows[-1]):
            rows.pop()

        if error_cells:
            warnings.append(
                f"Sheet '{sheet_name}': {error_cells} cell(s) held formula errors "
                "(#REF!, #DIV/0!, etc) — stored as null."
            )

        return {
            "name": sheet_name,
            "n_rows": len(rows),
            "n_cols": n_cols,
            "cells": rows,
            "partial": partial,
        }


def _safe_name(sheet):
    """Best-effort sheet name for an error message (never raises)."""
    try:
        return str(sheet.Name)
    except Exception:  # noqa: BLE001
        return "<unknown>"
