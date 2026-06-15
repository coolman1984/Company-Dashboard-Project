"""
server.py — a dependency-free MCP server for the Company Dashboard.

Speaks the Model Context Protocol over stdio using JSON-RPC 2.0 with
newline-delimited messages — the standard MCP stdio transport — implemented in
the Python standard library only, in keeping with the project's no-extra-deps
rule. It exposes the read-only tools defined in tools.py so an agent (via Claude
Code or any MCP client) can inspect the database, check extraction availability,
and search the knowledge wiki.

Run directly for a manual smoke check:
    python3 -m mcp_server.server        # then type JSON-RPC lines on stdin
Normally an MCP client launches it — see mcp_server/README.md and .mcp.json.

The message-handling logic is the pure function `handle_message`, so it is
fully unit-tested (test_mcp.py) without any transport.
"""
from __future__ import annotations

import json
import sys

try:
    from . import tools
except ImportError:  # allow `python3 server.py` from inside the folder
    import tools  # type: ignore

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "company-dashboard", "version": "1.0.0"}

# JSON-RPC error codes
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _public_tools():
    """tools/list payload — the registry without the Python handlers."""
    return [{"name": t["name"], "description": t["description"],
             "inputSchema": t["inputSchema"]} for t in tools.TOOLS]


def _call_tool(name, arguments):
    """Run a tool; return an MCP tools/call result dict (text content)."""
    tool = tools.TOOLS_BY_NAME.get(name)
    if tool is None:
        return {"content": [{"type": "text", "text": f"unknown tool: {name}"}],
                "isError": True}
    try:
        payload = tool["handler"](arguments or {})
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        return {"content": [{"type": "text", "text": text}], "isError": False}
    except tools.ToolError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    except Exception as exc:  # noqa: BLE001 — never crash the server on a tool bug
        return {"content": [{"type": "text", "text": f"tool failed: {exc}"}],
                "isError": True}


def handle_message(msg):
    """Dispatch one JSON-RPC message. Returns a response dict, or None for
    notifications (messages with no 'id')."""
    method = msg.get("method")
    req_id = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
        return _result(req_id, result)

    if method in ("notifications/initialized", "initialized"):
        return None  # client handshake notification; nothing to return

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": _public_tools()})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        if not name:
            return _error(req_id, INVALID_PARAMS, "tools/call requires 'name'")
        return _result(req_id, _call_tool(name, params.get("arguments")))

    # Unknown method: stay silent for notifications, error for requests.
    if is_notification:
        return None
    return _error(req_id, METHOD_NOT_FOUND, f"method not found: {method}")


def serve(stdin=None, stdout=None):
    """Read newline-delimited JSON-RPC from stdin, write responses to stdout."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue  # ignore malformed frames rather than crash the session
        response = handle_message(msg)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    serve()
