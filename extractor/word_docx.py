"""
word_docx.py - Word extractor (cross-platform, testable).

Reads .docx files with python-docx: paragraphs (with their style) and tables.
This runs anywhere. On Windows a COM-based Word extractor could be added for
legacy .doc files and richer fidelity, mirroring excel_com.py; the envelope
shape would stay identical.
"""
from __future__ import annotations

from .base import Extractor, optional_import


class WordDocxExtractor(Extractor):
    name = "word-docx"
    document_type = "document"
    extensions = (".docx",)

    def is_available(self):
        if optional_import("docx") is None:
            return False, "python-docx is not installed (pip install python-docx)"
        return True, "ok"

    def extract_content(self, path: str):
        import docx

        warnings = []
        document = docx.Document(path)

        paragraphs = [
            {"style": p.style.name if p.style else None, "text": p.text}
            for p in document.paragraphs
            if p.text and p.text.strip()
        ]
        tables = []
        for table in document.tables:
            tables.append({
                "rows": [[cell.text for cell in row.cells] for row in table.rows]
            })

        if not paragraphs and not tables:
            warnings.append("Document had no readable text or tables.")
        return {"paragraphs": paragraphs, "tables": tables}, warnings
