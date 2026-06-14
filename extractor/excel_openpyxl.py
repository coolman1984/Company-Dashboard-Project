"""
excel_openpyxl.py - cross-platform Excel extractor (the testable fallback).

Reads .xlsx / .xlsm workbooks with openpyxl. This runs anywhere (Linux, macOS,
Windows, CI) and needs no Microsoft Excel installed, so it is the path used for
automated tests. On a Windows machine with Excel, the COM extractor
(excel_com.py) is preferred for full fidelity and .xlsb support.
"""
from __future__ import annotations

from .base import Extractor, optional_import


class ExcelOpenpyxlExtractor(Extractor):
    name = "excel-openpyxl"
    document_type = "spreadsheet"
    extensions = (".xlsx", ".xlsm")

    def is_available(self):
        if optional_import("openpyxl") is None:
            return False, "openpyxl is not installed (pip install openpyxl)"
        return True, "ok"

    def extract_content(self, path: str):
        import openpyxl

        warnings = []
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheets = []
        try:
            for ws in workbook.worksheets:
                rows = []
                max_cols = 0
                for row in ws.iter_rows(values_only=True):
                    values = list(row)
                    # Trim wholly-empty trailing cells to keep the JSON tight.
                    while values and values[-1] is None:
                        values.pop()
                    rows.append([_clean(v) for v in values])
                    max_cols = max(max_cols, len(values))
                # Drop trailing fully-empty rows.
                while rows and not any(cell not in (None, "") for cell in rows[-1]):
                    rows.pop()
                sheets.append({
                    "name": ws.title,
                    "n_rows": len(rows),
                    "n_cols": max_cols,
                    "cells": rows,
                })
        finally:
            workbook.close()

        if not sheets:
            warnings.append("Workbook contained no readable sheets.")
        return {"sheets": sheets}, warnings


def _clean(value):
    """Make cell values JSON-friendly while preserving them faithfully."""
    import datetime as dt

    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    return value
