"""
pdf_text.py - digital-PDF extractor (text-based PDFs).

Reads text and simple tables from PDFs whose text is selectable (i.e. exported
from software, not scanned). Uses pdfplumber when available.

Scanned / photographed PDFs have NO selectable text - they are images. Those
need OCR (optical character recognition) and are handled by a separate,
later stage (see ROADMAP.md). When this extractor finds a page with no text it
records a warning so such files are flagged for the OCR path rather than
silently producing empty output.
"""
from __future__ import annotations

from .base import Extractor, optional_import


class PdfTextExtractor(Extractor):
    name = "pdf-text"
    document_type = "pdf"
    extensions = (".pdf",)

    def is_available(self):
        if optional_import("pdfplumber") is None:
            return False, "pdfplumber is not available (pip install pdfplumber)"
        return True, "ok"

    def extract_content(self, path: str):
        import pdfplumber

        warnings = []
        pages = []
        tables = []
        empty_pages = 0
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip():
                    empty_pages += 1
                pages.append({"number": index, "text": text})
                for table in page.extract_tables() or []:
                    tables.append({"page": index, "rows": table})

        if empty_pages:
            warnings.append(
                f"{empty_pages} page(s) had no selectable text - likely scanned; "
                "route to the OCR stage."
            )
        return {"pages": pages, "tables": tables}, warnings
