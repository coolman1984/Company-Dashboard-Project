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

from reports.definitions import REPORTS_BY_NAME
from reports.generate import compute_envelopes

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


def generate_report(args):
    """Run one named report and return its JSON envelope without writing files."""
    name = (args or {}).get("name", "").strip()
    if not name:
        raise ToolError("name is required")
    if name not in REPORTS_BY_NAME:
        raise ToolError(f"unknown report: {name}. Available: {sorted(REPORTS_BY_NAME)}")
    try:
        envelopes = compute_envelopes(DB_PATH, names=[name])
    except Exception as exc:  # noqa: BLE001 - report errors are surfaced to agent
        raise ToolError(f"report failed: {exc}")
    return envelopes[0]


def project_status(_args=None):
    """Current project state: git status, task board, database presence, test hints."""
    import subprocess
    status = {
        "db_exists": os.path.exists(DB_PATH),
        "db_path": DB_PATH,
        "knowledge_dir": KNOWLEDGE_DIR,
        "knowledge_exists": os.path.isdir(KNOWLEDGE_DIR),
    }
    # Git status (safe, read-only)
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        status["git_status"] = result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        status["git_status"] = None
    # Task board
    task_board_path = os.path.join(ROOT, "TASK_BOARD.md")
    if os.path.exists(task_board_path):
        with open(task_board_path, encoding="utf-8") as f:
            status["task_board"] = f.read()[:2000]  # First 2000 chars
    else:
        status["task_board"] = None
    # Test hints
    status["test_commands"] = [
        "npm test",
        "python3 test_db_schema.py",
        "python3 test_project_structure.py",
        "python3 -m mcp_server.test_mcp",
        "python3 -m brain.test_brain",
        "python3 -m reports.test_reports",
    ]
    return status


# Allow-listed test commands (safe, read-only or self-contained)
_ALLOWED_TESTS = {
    "npm_test": ["npm", "test"],
    "test_db_schema": ["python3", "test_db_schema.py"],
    "test_project_structure": ["python3", "test_project_structure.py"],
    "test_mcp": ["python3", "-m", "mcp_server.test_mcp"],
    "test_brain": ["python3", "-m", "brain.test_brain"],
    "test_reports": ["python3", "-m", "reports.test_reports"],
    "test_render": ["python3", "-m", "reports.test_render"],
    "test_scenario": ["python3", "-m", "reports.test_scenario"],
    "brain_check": ["python3", "-m", "brain.cli", "--check"],
}


def run_test(args):
    """Run one allow-listed test command. Args: {name}."""
    import subprocess
    name = (args or {}).get("name", "").strip()
    if not name:
        raise ToolError(f"name is required. Available: {sorted(_ALLOWED_TESTS)}")
    if name not in _ALLOWED_TESTS:
        raise ToolError(f"unknown test: {name}. Available: {sorted(_ALLOWED_TESTS)}")
    cmd = _ALLOWED_TESTS[name]
    try:
        result = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        return {
            "name": name,
            "command": " ".join(cmd),
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
            "stderr": result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr,
            "passed": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        raise ToolError(f"test {name} timed out (60s)")
    except Exception as exc:
        raise ToolError(f"test {name} failed: {exc}")


def brain_check(_args=None):
    """Validate the knowledge wiki: link integrity, orphans, tag index."""
    import subprocess
    try:
        result = subprocess.run(
            ["python3", "-m", "brain.cli", "--check"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()
        # Parse the output: "Notes: X | links: Y | tags: Z | orphans: W | broken links: V"
        stats = {}
        for part in output.split("|"):
            part = part.strip()
            if ":" in part:
                key, value = part.split(":", 1)
                stats[key.strip()] = value.strip()
        return {
            "passed": result.returncode == 0,
            "stats": stats,
            "output": output,
        }
    except Exception as exc:
        raise ToolError(f"brain check failed: {exc}")


def task_board_read(_args=None):
    """Read the current task board (TASK_BOARD.md) content."""
    task_board_path = os.path.join(ROOT, "TASK_BOARD.md")
    if not os.path.exists(task_board_path):
        return {"exists": False, "content": None}
    with open(task_board_path, encoding="utf-8") as f:
        content = f.read()
    return {"exists": True, "content": content}

# --------------------------------------------------------------------------- #
# EXTRACTION layer
# --------------------------------------------------------------------------- #
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
        "name": "generate_report",
        "description": "Run one named dashboard/report-engine report and return its JSON envelope without writing files. Useful for agents that need import_validation or a P&L report through MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Report name, e.g. import_validation, yearly_pl, outlook_pl."},
            },
            "required": ["name"],
        },
        "handler": generate_report,
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
    {
        "name": "project_status",
        "description": "Current project state: git status, task board, database presence, test hints. Useful for agents to understand the project context.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": project_status,
    },
    {
        "name": "run_test",
        "description": "Run one allow-listed test command (safe, read-only or self-contained). Returns exit code, stdout, stderr, and pass/fail status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Test name, e.g. npm_test, test_db_schema, test_brain, brain_check."},
            },
            "required": ["name"],
        },
        "handler": run_test,
    },
    {
        "name": "brain_check",
        "description": "Validate the knowledge wiki: link integrity, orphans, tag index. Returns stats and pass/fail status.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": brain_check,
    },
    {
        "name": "task_board_read",
        "description": "Read the current task board (TASK_BOARD.md) content. Returns the full Markdown content.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": task_board_read,
    },
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}
