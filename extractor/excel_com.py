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
via is_available() and falls back to the openpyxl extractor automatically.
Patterns here follow the project's hard-won COM lessons (see Agent.md):
DispatchEx, Visible/DisplayAlerts off, chunked reads, guaranteed Quit().
"""
from __future__ import annotations

import sys

from .base import Extractor, optional_import

CHUNK_ROWS = 5000  # Bulk-read this many rows per COM call for large sheets.


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
        import os

        import pythoncom
        import win32com.client

        warnings = []
        pythoncom.CoInitialize()
        excel = None
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Open(os.path.abspath(path), ReadOnly=True)
            sheets = []
            try:
                for sheet in workbook.Sheets:
                    sheets.append(self._read_sheet(sheet, warnings))
            finally:
                workbook.Close(SaveChanges=False)
        finally:
            if excel is not None:
                try:
                    excel.Quit()
                except Exception:  # noqa: BLE001
                    pass
            pythoncom.CoUninitialize()

        if not sheets:
            warnings.append("Workbook contained no readable sheets.")
        return {"sheets": sheets}, warnings

    def _read_sheet(self, sheet, warnings):
        used = sheet.UsedRange
        n_rows = int(used.Rows.Count)
        n_cols = int(used.Columns.Count)
        first_row = int(used.Row)
        first_col = int(used.Column)

        rows = []
        read = 0
        while read < n_rows:
            take = min(CHUNK_ROWS, n_rows - read)
            top = first_row + read
            block = sheet.Range(
                sheet.Cells(top, first_col),
                sheet.Cells(top + take - 1, first_col + n_cols - 1),
            ).Value
            # A 1x1 range comes back as a scalar; normalise to a grid.
            if not isinstance(block, tuple):
                block = ((block,),)
            for com_row in block:
                if not isinstance(com_row, tuple):
                    com_row = (com_row,)
                rows.append([_clean(v) for v in com_row])
            read += take

        while rows and not any(cell not in (None, "") for cell in rows[-1]):
            rows.pop()
        return {
            "name": str(sheet.Name),
            "n_rows": len(rows),
            "n_cols": n_cols,
            "cells": rows,
        }


def _clean(value):
    """Make COM cell values JSON-friendly (e.g. pywintypes datetimes)."""
    try:
        # pywintypes.TimeType exposes a .Format / isoformat-able value.
        import datetime as dt

        if isinstance(value, dt.datetime):
            return value.isoformat()
    except Exception:  # noqa: BLE001
        pass
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
