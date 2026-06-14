"""
outlook_msg.py - Outlook email extractor.

Handles saved Outlook messages (.msg) and plain .eml files: headers (from / to /
subject / date), the body text, and the list of attachments. Attachments are
recorded by name and type here; extracting the data *inside* an attachment is
done by re-feeding it through the engine (an .xlsx attachment goes to the Excel
extractor, etc.).

On Windows, a COM path against a live Outlook profile (reading a whole mailbox
or .pst) can be added later, mirroring excel_com.py; the envelope shape stays
the same. The .msg path uses the `extract-msg` library when available.
"""
from __future__ import annotations

from .base import Extractor, optional_import


class OutlookMsgExtractor(Extractor):
    name = "outlook-msg"
    document_type = "email"
    extensions = (".msg", ".eml")

    def is_available(self):
        if optional_import("extract_msg") is None:
            return False, "extract-msg is not installed (pip install extract-msg)"
        return True, "ok"

    def extract_content(self, path: str):
        import extract_msg

        warnings = []
        message = extract_msg.Message(path)
        try:
            headers = {
                "from": message.sender,
                "to": message.to,
                "cc": message.cc,
                "subject": message.subject,
                "date": str(message.date) if message.date else None,
            }
            body = message.body or ""
            attachments = [
                {
                    "filename": getattr(att, "longFilename", None)
                    or getattr(att, "shortFilename", None),
                    "bytes": len(att.data) if getattr(att, "data", None) else None,
                }
                for att in message.attachments
            ]
        finally:
            message.close()

        if not body.strip() and not attachments:
            warnings.append("Email had no body text or attachments.")
        return {"headers": headers, "body_text": body, "attachments": attachments}, warnings
