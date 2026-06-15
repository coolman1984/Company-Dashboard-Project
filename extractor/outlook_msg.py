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

import email
import os

from .base import Extractor, optional_import


class OutlookMsgExtractor(Extractor):
    name = "outlook-msg"
    document_type = "email"
    extensions = (".msg", ".eml")

    def is_available(self):
        # .eml files use stdlib email module - always available
        # .msg files need extract-msg library
        if optional_import("extract_msg") is None:
            return False, "extract-msg is not installed (pip install extract-msg)"
        return True, "ok"

    def extract_content(self, path: str):
        warnings = []
        
        # Guard: file size limit (100MB)
        file_size = os.path.getsize(path)
        if file_size > 100 * 1024 * 1024:
            warnings.append(
                f"File is very large ({file_size / (1024*1024):.1f} MB). "
                "Extraction may be slow or incomplete."
            )
        
        # Guard: empty file
        if file_size == 0:
            warnings.append("File is empty (0 bytes).")
            return {
                "headers": {},
                "body_text": "",
                "attachments": []
            }, warnings
        
        ext = os.path.splitext(path)[1].lower()
        
        # Handle .eml files with stdlib
        if ext == ".eml":
            return self._extract_eml(path, warnings)
        
        # Handle .msg files with extract-msg
        return self._extract_msg(path, warnings)
    
    def _extract_eml(self, path: str, warnings: list):
        """Extract from .eml files using stdlib email module."""
        try:
            with open(path, "rb") as f:
                msg = email.message_from_bytes(f.read())
        except Exception as exc:
            raise ValueError(
                f"Cannot parse .eml file: {exc}. File may be corrupt."
            ) from exc
        
        headers = {
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "cc": msg.get("Cc", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
        }
        
        body = ""
        attachments = []
        
        # Extract body and attachments
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Extract attachments
                if "attachment" in content_disposition:
                    filename = part.get_filename() or "unnamed_attachment"
                    payload = part.get_payload(decode=True)
                    attachments.append({
                        "filename": filename,
                        "bytes": len(payload) if payload else 0,
                    })
                # Extract text body
                elif content_type == "text/plain" and not body:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        body = part.get_payload(decode=True).decode(charset, errors="replace")
                    except Exception as exc:
                        warnings.append(f"Could not decode body: {exc}")
        else:
            # Single-part message
            try:
                charset = msg.get_content_charset() or "utf-8"
                body = msg.get_payload(decode=True).decode(charset, errors="replace")
            except Exception as exc:
                warnings.append(f"Could not decode body: {exc}")
        
        if not body.strip() and not attachments:
            warnings.append("Email had no body text or attachments.")
        
        return {
            "headers": headers,
            "body_text": body,
            "attachments": attachments
        }, warnings
    
    def _extract_msg(self, path: str, warnings: list):
        """Extract from .msg files using extract-msg library."""
        import extract_msg
        
        try:
            message = extract_msg.Message(path)
        except Exception as exc:
            raise ValueError(
                f"Cannot open .msg file: {exc}. File may be corrupt or encrypted."
            ) from exc
        
        try:
            headers = {
                "from": message.sender,
                "to": message.to,
                "cc": message.cc,
                "subject": message.subject,
                "date": str(message.date) if message.date else None,
            }
            body = message.body or ""
            attachments = []
            
            for att_idx, att in enumerate(message.attachments, start=1):
                try:
                    filename = (
                        getattr(att, "longFilename", None)
                        or getattr(att, "shortFilename", None)
                        or f"attachment_{att_idx}"
                    )
                    att_size = len(att.data) if getattr(att, "data", None) else 0
                    attachments.append({
                        "filename": filename,
                        "bytes": att_size,
                    })
                except Exception as exc:
                    warnings.append(f"Attachment {att_idx}: could not read ({exc})")
        finally:
            message.close()

        if not body.strip() and not attachments:
            warnings.append("Email had no body text or attachments.")
        
        return {
            "headers": headers,
            "body_text": body,
            "attachments": attachments
        }, warnings
