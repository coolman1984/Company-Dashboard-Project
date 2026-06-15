"""
csv_text.py - CSV / TSV extractor with Arabic-safe encoding detection.

Plain-text exports are the highest-risk format for Arabic: they are often saved
as Windows-1256 (the legacy Arabic code page) or as UTF-8 with or without a BOM,
and getting the encoding wrong turns Arabic into mojibake. This extractor sniffs
the encoding (BOM -> UTF-8 -> Windows-1256 -> Latin-1) and the delimiter, then
captures the rows into the same spreadsheet envelope the Excel extractors use, so
a CSV loads through the mapper exactly like a workbook sheet.

Pure standard library - always available, no third-party dependency.
"""
from __future__ import annotations

import csv
import io
import os

from .base import Extractor


class CsvTextExtractor(Extractor):
    name = "csv-text"
    document_type = "spreadsheet"
    extensions = (".csv", ".tsv")

    def is_available(self):
        return True, "ok"

    def extract_content(self, path: str):
        warnings = []
        
        # Guard: file size limit (100MB)
        file_size = os.path.getsize(path)
        if file_size > 100 * 1024 * 1024:
            warnings.append(
                f"File is very large ({file_size / (1024*1024):.1f} MB). "
                "CSV parsing may be slow."
            )
        
        # Guard: empty file
        if file_size == 0:
            warnings.append("File is empty (0 bytes).")
            sheet = {
                "name": os.path.splitext(os.path.basename(path))[0],
                "n_rows": 0,
                "n_cols": 0,
                "cells": [],
            }
            return {"sheets": [sheet]}, warnings
        
        with open(path, "rb") as handle:
            raw_bytes = handle.read()

        text, encoding = _decode(raw_bytes)
        if encoding not in ("utf-8", "utf-8-sig"):
            warnings.append(
                f"Decoded as {encoding} (no UTF-8 BOM). Verify Arabic text looks correct.")
        
        # Guard: binary content detection
        if _looks_binary(raw_bytes):
            warnings.append(
                "File appears to contain binary data. This may not be a valid CSV.")

        delimiter = _sniff_delimiter(text, path)
        
        try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = []
            parse_errors = 0
            for line_num, row in enumerate(reader, start=1):
                try:
                    cleaned = [_clean(v) for v in row]
                    rows.append(cleaned)
                except Exception as exc:
                    parse_errors += 1
                    if parse_errors <= 5:  # Don't spam warnings
                        warnings.append(f"Line {line_num}: parse error ({exc})")
            
            if parse_errors > 5:
                warnings.append(f"... and {parse_errors - 5} more parse errors")
        except csv.Error as exc:
            raise ValueError(
                f"CSV parsing failed: {exc}. File may be malformed or use "
                "an unsupported format."
            ) from exc
        
        while rows and not any(cell not in (None, "") for cell in rows[-1]):
            rows.pop()

        if not rows:
            warnings.append("File contained no rows.")
        sheet = {
            "name": os.path.splitext(os.path.basename(path))[0],
            "n_rows": len(rows),
            "n_cols": max((len(r) for r in rows), default=0),
            "cells": rows,
        }
        return {"sheets": [sheet]}, warnings


def _decode(raw_bytes: bytes):
    """Return (text, encoding_used), trying the encodings Arabic CSVs use."""
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return raw_bytes.decode("utf-8-sig"), "utf-8-sig"
    if raw_bytes[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw_bytes.decode("utf-16"), "utf-16"
    try:
        return raw_bytes.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        # Windows-1256 is the common legacy Arabic code page.
        return raw_bytes.decode("cp1256"), "cp1256"
    except UnicodeDecodeError:
        # Last resort: never crash on a stray byte.
        return raw_bytes.decode("latin-1"), "latin-1"


def _looks_binary(raw_bytes: bytes) -> bool:
    """Heuristic: detect if file contains too many non-printable bytes."""
    # Sample first 10KB
    sample = raw_bytes[:10240]
    if not sample:
        return False
    
    # Count non-printable, non-whitespace bytes
    non_printable = sum(
        1 for byte in sample
        if byte < 32 and byte not in (9, 10, 13)  # tab, newline, carriage return
    )
    
    # If >10% non-printable, likely binary
    return (non_printable / len(sample)) > 0.1


def _sniff_delimiter(text: str, path: str) -> str:
    if os.path.splitext(path)[1].lower() == ".tsv":
        return "\t"
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        first_line = next((ln for ln in sample.splitlines() if ln.strip()), "")
        counts = {d: first_line.count(d) for d in (",", ";", "\t", "|")}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def _clean(value):
    """CSV cells are text; preserve them faithfully, normalising only newlines."""
    if isinstance(value, str):
        # Normalize line endings
        cleaned = value.replace("\r\n", "\n").replace("\r", "\n")
        # Strip excessive whitespace but preserve internal structure
        # Don't strip leading/trailing - it might be intentional (Arabic RTL)
        return cleaned
    return value
