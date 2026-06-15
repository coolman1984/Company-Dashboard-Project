"""
excel_openpyxl.py - cross-platform Excel extractor (the testable fallback).

Reads .xlsx / .xlsm workbooks with openpyxl. This runs anywhere (Linux, macOS,
Windows, CI) and needs no Microsoft Excel installed, so it is the path used for
automated tests. On a Windows machine with Excel, the COM extractor
(excel_com.py) is preferred for full fidelity and .xlsb support.
"""
from __future__ import annotations

import os

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
        
        # Guard: file size limit (50MB)
        file_size = os.path.getsize(path)
        if file_size > 50 * 1024 * 1024:
            warnings.append(
                f"File is very large ({file_size / (1024*1024):.1f} MB). "
                "Extraction may be slow or incomplete."
            )
        
        try:
            workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        except Exception as exc:
            raise ValueError(
                f"Cannot open workbook: {exc}. File may be corrupt, encrypted, "
                "or not a valid Excel file."
            ) from exc
        
        sheets = []
        try:
            for ws in workbook.worksheets:
                sheet_name = ws.title
                rows = []
                max_cols = 0
                error_cells = 0
                hidden_rows = 0
                
                try:
                    row_idx = 0
                    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                        values = list(row)
                        # Trim wholly-empty trailing cells to keep the JSON tight.
                        while values and values[-1] is None:
                            values.pop()
                        
                        cleaned = []
                        for cell in values:
                            clean_val, had_error = _clean(cell)
                            cleaned.append(clean_val)
                            if had_error:
                                error_cells += 1
                        
                        rows.append(cleaned)
                        max_cols = max(max_cols, len(values))
                except Exception as exc:
                    warnings.append(
                        f"Sheet '{sheet_name}': stopped reading at row {row_idx} "
                        f"due to error: {exc}. Partial extraction."
                    )
                
                # Drop trailing fully-empty rows.
                while rows and not any(cell not in (None, "") for cell in rows[-1]):
                    rows.pop()
                
                sheets.append({
                    "name": sheet_name,
                    "n_rows": len(rows),
                    "n_cols": max_cols,
                    "cells": rows,
                })
                
                if error_cells > 0:
                    warnings.append(
                        f"Sheet '{sheet_name}': {error_cells} cell(s) contained "
                        "formula errors (#REF!, #DIV/0!, etc) - converted to null."
                    )
        finally:
            workbook.close()

        if not sheets:
            warnings.append("Workbook contained no readable sheets.")
        return {"sheets": sheets}, warnings


def _clean(value):
    """Make cell values JSON-friendly while preserving them faithfully.
    
    Returns (cleaned_value, had_error) where had_error is True if the cell
    contained a formula error like #REF! or #DIV/0!.
    """
    import datetime as dt

    # Handle formula errors - openpyxl returns these as strings
    if isinstance(value, str) and value.startswith("#"):
        error_markers = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#NULL!", "#N/A", "#NUM!")
        if value in error_markers:
            return None, True  # Convert to null, flag as error
    
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat(), False
    return value, False
