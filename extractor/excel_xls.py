"""
excel_xls.py - reader for legacy .xls (Excel 97-2003) workbooks.

Old Arabic accounting systems still export .xls, which openpyxl cannot read.
This xlrd-based extractor handles them cross-platform; on Windows the COM
extractor is still preferred. Produces the same spreadsheet envelope as the
other extractors.

Dependency (xlrd) is optional: if missing, the engine reports this extractor as
unavailable and falls back rather than crashing. Note xlrd>=2.0 reads .xls only
(it dropped .xlsx), which is exactly the role it plays here.
"""
from __future__ import annotations

import os

from .base import Extractor, optional_import


class ExcelXlsExtractor(Extractor):
    name = "excel-xls"
    document_type = "spreadsheet"
    extensions = (".xls",)

    def is_available(self):
        if optional_import("xlrd") is None:
            return False, "xlrd is not installed (pip install xlrd)"
        return True, "ok"

    def extract_content(self, path: str):
        import xlrd

        warnings = []
        
        # Guard: file size limit (50MB)
        file_size = os.path.getsize(path)
        if file_size > 50 * 1024 * 1024:
            warnings.append(
                f"File is very large ({file_size / (1024*1024):.1f} MB). "
                "Extraction may be slow or incomplete."
            )
        
        # Guard: empty file
        if file_size == 0:
            warnings.append("File is empty (0 bytes).")
            return {"sheets": []}, warnings
        
        try:
            book = xlrd.open_workbook(path)
        except Exception as exc:
            raise ValueError(
                f"Cannot open .xls workbook: {exc}. File may be corrupt, "
                "encrypted, or not a valid Excel 97-2003 file."
            ) from exc
        
        sheets = []
        for sheet in book.sheets():
            try:
                rows = []
                row_errors = 0
                for row_index in range(sheet.nrows):
                    try:
                        values = list(sheet.row_values(row_index))
                        while values and values[-1] in (None, ""):
                            values.pop()
                        rows.append([_clean(v) for v in values])
                    except Exception as exc:
                        row_errors += 1
                        if row_errors <= 3:
                            warnings.append(
                                f"Sheet '{sheet.name}' row {row_index + 1}: {exc}"
                            )
                
                if row_errors > 3:
                    warnings.append(
                        f"Sheet '{sheet.name}': ... and {row_errors - 3} more row errors"
                    )
                
                while rows and not any(c not in (None, "") for c in rows[-1]):
                    rows.pop()
                sheets.append({
                    "name": sheet.name,
                    "n_rows": len(rows),
                    "n_cols": sheet.ncols,
                    "cells": rows,
                })
            except Exception as exc:
                warnings.append(f"Sheet '{sheet.name}': could not read ({exc})")

        if not sheets:
            warnings.append("Workbook contained no readable sheets.")
        else:
            warnings.append(
                "xlrd returns dates as serial numbers; date columns may need "
                "explicit handling in the mapping.")
        return {"sheets": sheets}, warnings


def _clean(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
