"""
registry.py - which extractor handles which file.

Extractors are listed in priority order. For a given file, the engine picks the
FIRST one that both handles the extension and is currently available. This is
how the Windows COM "full control" path is preferred when present, while the
cross-platform fallbacks keep the engine working everywhere else.
"""
from __future__ import annotations

from .excel_com import ExcelComExtractor
from .excel_openpyxl import ExcelOpenpyxlExtractor
from .outlook_msg import OutlookMsgExtractor
from .pdf_text import PdfTextExtractor
from .word_docx import WordDocxExtractor

# Order matters: COM Excel before openpyxl Excel.
EXTRACTORS = [
    ExcelComExtractor(),
    ExcelOpenpyxlExtractor(),
    WordDocxExtractor(),
    PdfTextExtractor(),
    OutlookMsgExtractor(),
]


def select_extractor(path):
    """Return (extractor, reason).

    - (extractor, "ok")               an available extractor was found
    - (None, "unsupported")           no extractor handles this file type
    - (None, "<why unavailable>")     the right extractor exists but its
                                      dependency/OS is missing
    """
    matched = [e for e in EXTRACTORS if e.handles(path)]
    if not matched:
        return None, "unsupported"
    reasons = []
    for extractor in matched:
        available, reason = extractor.is_available()
        if available:
            return extractor, "ok"
        reasons.append(f"{extractor.name}: {reason}")
    return None, "; ".join(reasons)


def describe_availability():
    """List every extractor and whether it can run right now."""
    rows = []
    for extractor in EXTRACTORS:
        available, reason = extractor.is_available()
        rows.append({
            "name": extractor.name,
            "extensions": list(extractor.extensions),
            "document_type": extractor.document_type,
            "available": available,
            "reason": reason,
        })
    return rows
