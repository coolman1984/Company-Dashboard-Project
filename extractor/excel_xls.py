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
        book = xlrd.open_workbook(path)
        sheets = []
        for sheet in book.sheets():
            rows = []
            for row_index in range(sheet.nrows):
                values = list(sheet.row_values(row_index))
                while values and values[-1] in (None, ""):
                    values.pop()
                rows.append([_clean(v) for v in values])
            while rows and not any(c not in (None, "") for c in rows[-1]):
                rows.pop()
            sheets.append({
                "name": sheet.name,
                "n_rows": len(rows),
                "n_cols": sheet.ncols,
                "cells": rows,
            })

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
