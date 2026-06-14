"""
manifest.py - the append-only processing ledger.

Every file the engine processes appends one JSON line to raw/manifest.jsonl:
what it was, its fingerprint, which extractor ran, the result, and where the raw
capture landed. This is the audit trail ("what did we take from the client, and
when?") and it lets the engine skip files it has already captured unchanged.
"""
from __future__ import annotations

import datetime as _dt
import json
import os

MANIFEST_NAME = "manifest.jsonl"


def manifest_path(out_dir: str) -> str:
    return os.path.join(out_dir, MANIFEST_NAME)


def load_seen_hashes(out_dir: str) -> set:
    """Return the set of source sha256s already captured successfully."""
    path = manifest_path(out_dir)
    seen = set()
    if not os.path.exists(path):
        return seen
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("status") == "ok" and entry.get("sha256"):
                seen.add(entry["sha256"])
    return seen


def append(out_dir: str, entry: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    entry = {"logged_at": _dt.datetime.now(_dt.timezone.utc)
             .strftime("%Y-%m-%dT%H:%M:%SZ"), **entry}
    with open(manifest_path(out_dir), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
