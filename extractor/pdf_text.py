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

import os

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
        
        # Guard: file size limit (200MB)
        file_size = os.path.getsize(path)
        if file_size > 200 * 1024 * 1024:
            warnings.append(
                f"File is very large ({file_size / (1024*1024):.1f} MB). "
                "PDF extraction may be slow or incomplete."
            )
        
        # Guard: encrypted/password-protected PDFs
        try:
            pdf = pdfplumber.open(path)
        except Exception as exc:
            error_msg = str(exc).lower()
            if "password" in error_msg or "encrypt" in error_msg:
                raise ValueError(
                    f"PDF is password-protected or encrypted. "
                    f"Cannot extract without password. Error: {exc}"
                ) from exc
            raise ValueError(
                f"Cannot open PDF: {exc}. File may be corrupt or not a valid PDF."
            ) from exc
        
        pages = []
        tables = []
        empty_pages = 0
        total_pages = len(pdf.pages)
        parse_errors = 0
        
        try:
            for index, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text() or ""
                    if not text.strip():
                        empty_pages += 1
                    pages.append({"number": index, "text": text})
                    
                    # Extract tables from this page
                    try:
                        for table in page.extract_tables() or []:
                            tables.append({"page": index, "rows": table})
                    except Exception as exc:
                        parse_errors += 1
                        if parse_errors <= 3:
                            warnings.append(
                                f"Page {index}: table extraction failed ({exc}). "
                                "Text was still captured."
                            )
                except Exception as exc:
                    parse_errors += 1
                    if parse_errors <= 5:
                        warnings.append(
                            f"Page {index}: extraction error ({exc}). "
                            "Page skipped."
                        )
                    # Add empty page placeholder so page numbers stay consistent
                    pages.append({"number": index, "text": ""})
        finally:
            pdf.close()
        
        if parse_errors > 5:
            warnings.append(f"... and {parse_errors - 5} more extraction errors")

        if empty_pages:
            if empty_pages == total_pages:
                warnings.append(
                    f"ALL {empty_pages} page(s) had no selectable text - "
                    "this is likely a scanned PDF. Route to the OCR stage."
                )
            elif empty_pages > total_pages * 0.5:
                warnings.append(
                    f"{empty_pages} of {total_pages} page(s) had no selectable text - "
                    "many pages may be scanned. Consider OCR for better results."
                )
            else:
                warnings.append(
                    f"{empty_pages} page(s) had no selectable text - likely scanned; "
                    "route to the OCR stage."
                )
        
        # Guard: completely empty PDF
        if not pages:
            warnings.append("PDF contained no pages.")
        
        return {"pages": pages, "tables": tables}, warnings
