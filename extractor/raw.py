"""
raw.py - the "save the original faithfully as JSON" layer.

Every source file, regardless of type, is captured into a single common
envelope so the original is preserved exactly and auditably before any
interpretation happens. Extractors only fill in the type-specific `content`;
this module stamps the universal metadata around it.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re

SCHEMA_VERSION = 1


def sha256_of(path: str) -> str:
    """Stable fingerprint of the source file (also used to detect re-runs)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_envelope(path, intake_root, extractor_name, document_type, content, warnings=None):
    """Wrap extractor output in the universal raw-document envelope."""
    stat = os.stat(path)
    relpath = os.path.relpath(path, intake_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "filename": os.path.basename(path),
            "relpath": relpath.replace(os.sep, "/"),
            "bytes": stat.st_size,
            "sha256": sha256_of(path),
            "extension": os.path.splitext(path)[1].lower(),
            "modified_at": _dt.datetime.fromtimestamp(
                stat.st_mtime, _dt.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "extractor": extractor_name,
        "extracted_at": _utc_now_iso(),
        "document_type": document_type,
        "content": content,
        "warnings": list(warnings or []),
    }


def raw_output_name(envelope: dict) -> str:
    """Deterministic, collision-safe filename for a raw capture."""
    relpath = envelope["source"]["relpath"]
    short_hash = envelope["source"]["sha256"][:8]
    flat = re.sub(r"[^A-Za-z0-9._-]+", "_", relpath)
    return f"{flat}.{short_hash}.raw.json"
