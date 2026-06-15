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
        with open(path, "rb") as handle:
            raw_bytes = handle.read()

        text, encoding = _decode(raw_bytes)
        if encoding not in ("utf-8", "utf-8-sig"):
            warnings.append(
                f"Decoded as {encoding} (no UTF-8 BOM). Verify Arabic text looks correct.")

        delimiter = _sniff_delimiter(text, path)
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [[_clean(v) for v in row] for row in reader]
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
        return value.replace("\r\n", "\n").replace("\r", "\n")
    return value
