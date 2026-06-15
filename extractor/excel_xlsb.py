"""
excel_xlsb.py - cross-platform reader for binary .xlsb workbooks.

.xlsb is Excel's binary format; pure-Python openpyxl cannot read it. On Windows
the COM extractor is preferred (full fidelity), but on Linux/CI this pyxlsb-based
reader lets us handle the large binary workbooks the project deals with without
Excel installed. Produces the same spreadsheet envelope as the other extractors.

Dependency (pyxlsb) is optional: if missing, the engine reports this extractor as
unavailable and falls back rather than crashing.
"""
from __future__ import annotations

import datetime as dt
import os

from .base import Extractor, optional_import


class ExcelXlsbExtractor(Extractor):
    name = "excel-xlsb"
    document_type = "spreadsheet"
    extensions = (".xlsb",)

    def is_available(self):
        if optional_import("pyxlsb") is None:
            return False, "pyxlsb is not installed (pip install pyxlsb)"
        return True, "ok"

    def extract_content(self, path: str):
        from pyxlsb import open_workbook

        warnings = []
        
        # Guard: file size limit (100MB)
        file_size = os.path.getsize(path)
        if file_size > 100 * 1024 * 1024:
            warnings.append(
                f"File is very large ({file_size / (1024*1024):.1f} MB). "
                "Extraction may be slow or incomplete."
            )
        
        # Guard: empty file
        if file_size == 0:
            warnings.append("File is empty (0 bytes).")
            return {"sheets": []}, warnings
        
        sheets = []
        try:
            with open_workbook(path) as workbook:
                for sheet_name in workbook.sheets:
                    try:
                        with workbook.get_sheet(sheet_name) as sheet:
                            rows = []
                            max_cols = 0
                            row_errors = 0
                            for row_idx, row in enumerate(sheet.rows(), start=1):
                                try:
                                    values = [cell.v for cell in row]
                                    while values and values[-1] is None:
                                        values.pop()
                                    rows.append([_clean(v) for v in values])
                                    max_cols = max(max_cols, len(values))
                                except Exception as exc:
                                    row_errors += 1
                                    if row_errors <= 3:
                                        warnings.append(
                                            f"Sheet '{sheet_name}' row {row_idx}: {exc}"
                                        )
                            
                            if row_errors > 3:
                                warnings.append(
                                    f"Sheet '{sheet_name}': ... and {row_errors - 3} more row errors"
                                )
                            
                            while rows and not any(c not in (None, "") for c in rows[-1]):
                                rows.pop()
                            sheets.append({
                                "name": str(sheet_name),
                                "n_rows": len(rows),
                                "n_cols": max_cols,
                                "cells": rows,
                            })
                    except Exception as exc:
                        warnings.append(f"Sheet '{sheet_name}': could not read ({exc})")
        except Exception as exc:
            raise ValueError(
                f"Cannot open .xlsb workbook: {exc}. File may be corrupt or encrypted."
            ) from exc

        if not sheets:
            warnings.append("Workbook contained no readable sheets.")
        else:
            warnings.append(
                "pyxlsb returns dates as numbers; date columns may need explicit "
                "handling in the mapping. Prefer the COM extractor on Windows.")
        return {"sheets": sheets}, warnings


def _clean(value):
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
