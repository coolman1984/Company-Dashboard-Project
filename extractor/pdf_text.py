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

# OCR is an OPTIONAL fallback for scanned/photographed PDF pages (no selectable
# text). It needs pytesseract + Pillow AND the system `tesseract` binary, so it
# degrades gracefully: if any piece is missing we simply flag the page for OCR
# (the previous behaviour) instead of failing. Language data: English + Arabic.
OCR_LANG = os.environ.get("OCR_LANG", "eng+ara")


def ocr_available():
    """True only if pytesseract, Pillow and the tesseract binary are all present."""
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 — any failure means "OCR not usable"
        return False


def _ocr_page(page):
    """Best-effort OCR text for one pdfplumber page; '' if it can't be done."""
    import pytesseract
    img = page.to_image(resolution=200).original
    try:
        return pytesseract.image_to_string(img, lang=OCR_LANG)
    except Exception:  # noqa: BLE001 — e.g. missing Arabic traineddata
        return pytesseract.image_to_string(img)   # fall back to default language


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
        ocr_pages = 0
        ocr_on = ocr_available()
        total_pages = len(pdf.pages)
        parse_errors = 0

        try:
            for index, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text() or ""
                    used_ocr = False
                    # Scanned page with no selectable text: OCR it if we can.
                    if not text.strip() and ocr_on:
                        try:
                            ocr_text = _ocr_page(page)
                            if ocr_text.strip():
                                text = ocr_text
                                used_ocr = True
                                ocr_pages += 1
                        except Exception as exc:  # noqa: BLE001
                            parse_errors += 1
                            if parse_errors <= 5:
                                warnings.append(f"Page {index}: OCR failed ({exc}).")
                    if not text.strip():
                        empty_pages += 1
                    pages.append({"number": index, "text": text, "ocr": used_ocr})
                    
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

        if ocr_pages:
            warnings.append(f"OCR recovered text from {ocr_pages} scanned page(s).")
        if empty_pages and not ocr_on:
            warnings.append("OCR is not installed (pip install pytesseract Pillow + the "
                            "tesseract binary); scanned pages were left empty.")

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
