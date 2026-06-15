# mcp_server — agent tool access (harness layer)

A dependency-free **Model Context Protocol** server that gives an AI agent
safe, **read-only** access to the project's layers. It is the bridge described
in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §4 — it lets the harness *act on*
the system through defined tools instead of guessing.

It speaks MCP over stdio (newline-delimited JSON-RPC 2.0) using the Python
standard library only — no extra dependencies, works offline, consistent with
the project's minimal-dependency rule.

## Tools

| Tool | Layer | What it returns |
|------|-------|-----------------|
| `db_overview` | data | columns, views, row count, years, versions |
| `run_select` | data | rows from ONE read-only `SELECT` (max 500 rows; writes/PRAGMA/ATTACH rejected) |
| `pl_summary` | data | the yearly Actual P&L roll-up (`v_yearly_pl`) |
| `extractor_availability` | extraction | which file-type extractors can run now |
| `wiki_search` | second brain | notes matching a term, with snippets |
| `wiki_get` | second brain | one knowledge note's Markdown |

Every tool is read-only — nothing mutates the database, files, or anything else.
The tool logic lives in `tools.py` (pure, unit-tested); `server.py` is just the
transport.

## Connect it to Claude Code

The repo ships a project-scoped [`../.mcp.json`](../.mcp.json), so from the
project root:

```bash
claude mcp list           # should show "company-dashboard"
```

…or add it to any MCP client manually:

```json
{
  "mcpServers": {
    "company-dashboard": { "command": "python3", "args": ["-m", "mcp_server.server"] }
  }
}
```

The server must be launched from the repository root (it imports the project's
`db_schema` and `extractor` modules and reads `pl_detail.db` / `knowledge/`).

## Manual smoke check

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python3 -m mcp_server.server
```

## Tests

```bash
python3 -m mcp_server.test_mcp     # tools + JSON-RPC dispatch (no MCP runtime needed)
```
