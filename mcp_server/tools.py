"""
tools.py — the capabilities the MCP server exposes to an agent (layer 5).

Pure, read-only functions over the existing layers:
  * DATA      — inspect the schema, run guarded read-only SELECTs, P&L summary
  * EXTRACTION — which extractors are available right now
  * SECOND BRAIN — search and read the Obsidian-style wiki in knowledge/

Everything here is dependency-free and unit-tested on any platform. The MCP
transport (server.py) is a thin wrapper that calls these. Keeping the logic
here means the valuable part is tested without needing the MCP runtime.

Design rules (see ARCHITECTURE.md): the agent may only READ. No tool mutates
the database, the filesystem, or anything else.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys

# This package lives one level below the repo root; make the root importable so
# we can reuse the canonical modules (no duplicated schema/extractor logic).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import db_schema  # noqa: E402  (after sys.path tweak)

DB_PATH = os.path.join(ROOT, "pl_detail.db")
KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")

MAX_ROWS = 500
DEFAULT_ROWS = 100

# Read-only SELECTs only. The connection is opened read-only too (defence in
# depth), but we reject obviously-unsafe statements up front for a clear error.
_FORBIDDEN = ("attach", "detach", "pragma", "insert", "update", "delete",
              "drop", "create", "alter", "replace", "vacuum", "reindex")


class ToolError(Exception):
    """Raised when a tool cannot run; surfaced to the agent as an error result."""


# --------------------------------------------------------------------------- #
# DATA layer
# --------------------------------------------------------------------------- #
def _connect_ro():
    if not os.path.exists(DB_PATH):
        raise ToolError(
            f"database not found at {DB_PATH}. Build it first "
            "(python3 seed_db.py --force, or an ingest).")
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def db_overview(_args=None):
    """Schema + coverage of the live database (columns, views, rows, years)."""
    overview = {
        "db_path": DB_PATH,
        "columns": db_schema.column_names(),
        "views": list(db_schema.EXPECTED_VIEWS),
    }
    conn = _connect_ro()
    try:
        overview["row_count"] = conn.execute("SELECT COUNT(*) FROM pl_detail").fetchone()[0]
        overview["years"] = [r[0] for r in conn.execute(
            "SELECT DISTINCT year FROM pl_detail WHERE year IS NOT NULL ORDER BY year")]
        overview["versions"] = [r[0] for r in conn.execute(
            "SELECT DISTINCT version FROM pl_detail WHERE version IS NOT NULL ORDER BY version")]
    finally:
        conn.close()
    return overview


def _enforce_select(sql):
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise ToolError("empty query")
    if ";" in statement:
        raise ToolError("only a single statement is allowed (no ';').")
    low = statement.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise ToolError("only read-only SELECT/WITH queries are allowed.")
    for word in _FORBIDDEN:
        if re.search(r"\b" + word + r"\b", low):
            raise ToolError(f"keyword '{word}' is not allowed (read-only access).")
    return statement


def run_select(args):
    """Run one read-only SELECT against pl_detail.db. Args: {sql, limit?}."""
    sql = (args or {}).get("sql", "")
    limit = int((args or {}).get("limit", DEFAULT_ROWS))
    limit = max(1, min(limit, MAX_ROWS))
    statement = _enforce_select(sql)
    if not re.search(r"\blimit\b", statement.lower()):
        statement = f"{statement} LIMIT {limit}"
    conn = _connect_ro()
    try:
        cur = conn.execute(statement)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [list(r) for r in cur.fetchall()]
    except sqlite3.Error as exc:
        raise ToolError(f"SQL error: {exc}")
    finally:
        conn.close()
    return {"columns": columns, "row_count": len(rows), "rows": rows}


def pl_summary(_args=None):
    """The yearly Actual P&L roll-up (from v_yearly_pl)."""
    conn = _connect_ro()
    try:
        cur = conn.execute("SELECT * FROM v_yearly_pl ORDER BY year")
        columns = [d[0] for d in cur.description]
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    return {"columns": columns, "years": rows}


# --------------------------------------------------------------------------- #
# EXTRACTION layer
# --------------------------------------------------------------------------- #
def extractor_availability(_args=None):
    """Which file-type extractors can run right now (COM on Windows, etc.)."""
    from extractor import registry
    return {"extractors": registry.describe_availability()}


# --------------------------------------------------------------------------- #
# SECOND BRAIN (wiki) layer
# --------------------------------------------------------------------------- #
def _safe_note_path(note):
    """Resolve a note name to a path strictly inside knowledge/ (no traversal)."""
    name = note if note.endswith(".md") else note + ".md"
    target = os.path.normpath(os.path.join(KNOWLEDGE_DIR, name))
    base = os.path.normpath(KNOWLEDGE_DIR)
    if os.path.commonpath([target, base]) != base:
        raise ToolError("note path escapes the knowledge/ directory.")
    return target


def _iter_notes():
    if not os.path.isdir(KNOWLEDGE_DIR):
        return
    for dirpath, _dirs, files in os.walk(KNOWLEDGE_DIR):
        for fname in files:
            if fname.endswith(".md"):
                yield os.path.join(dirpath, fname)


def wiki_search(args):
    """Search the knowledge wiki. Args: {query, limit?}. Returns matches + snippets."""
    query = (args or {}).get("query", "").strip()
    limit = max(1, min(int((args or {}).get("limit", 10)), 50))
    if not query:
        raise ToolError("query is required")
    needle = query.lower()
    matches = []
    for path in sorted(_iter_notes()):
        rel = os.path.relpath(path, ROOT)
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            continue
        hay = text.lower()
        if needle in os.path.basename(path).lower() or needle in hay:
            idx = hay.find(needle)
            snippet = ""
            if idx >= 0:
                start = max(0, idx - 60)
                snippet = text[start:idx + 120].replace("\n", " ").strip()
            matches.append({"note": rel, "snippet": snippet})
        if len(matches) >= limit:
            break
    return {"query": query, "match_count": len(matches), "matches": matches}


def wiki_get(args):
    """Read one wiki note. Args: {note}. Returns its Markdown content."""
    note = (args or {}).get("note", "").strip()
    if not note:
        raise ToolError("note is required")
    path = _safe_note_path(note)
    if not os.path.isfile(path):
        raise ToolError(f"note not found: {note}")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return {"note": os.path.relpath(path, ROOT), "content": text}


# --------------------------------------------------------------------------- #
# Tool registry — the single list the MCP server exposes.
# --------------------------------------------------------------------------- #
TOOLS = [
    {
        "name": "db_overview",
        "description": "Schema and coverage of the live P&L database: columns, "
                       "views, total rows, the years and versions present.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": db_overview,
    },
    {
        "name": "run_select",
        "description": "Run ONE read-only SELECT query against the P&L ledger "
                       "(pl_detail.db). Returns columns and rows. Max "
                       f"{MAX_ROWS} rows; writes/PRAGMA/ATTACH are rejected.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A single SELECT/WITH query."},
                "limit": {"type": "integer", "description": f"Row cap (<= {MAX_ROWS})."},
            },
            "required": ["sql"],
        },
        "handler": run_select,
    },
    {
        "name": "pl_summary",
        "description": "The yearly Actual profit-and-loss roll-up (v_yearly_pl).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": pl_summary,
    },
    {
        "name": "extractor_availability",
        "description": "List the file-type extractors and whether each can run "
                       "in the current environment (e.g. Excel COM on Windows).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": extractor_availability,
    },
    {
        "name": "wiki_search",
        "description": "Search the Obsidian-style knowledge wiki (the project's "
                       "second brain) for a term; returns matching notes + snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
        "handler": wiki_search,
    },
    {
        "name": "wiki_get",
        "description": "Read one knowledge-wiki note by name (e.g. 'glossary' or "
                       "'processes/data-pipeline'). Returns its Markdown.",
        "inputSchema": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
        },
        "handler": wiki_get,
    },
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}
