# Company Dashboard — Portable Edition

This folder is **fully self-contained**. It runs on any Windows 11 (x64) PC with **no installation** — no Node.js, no admin rights, nothing.

## How to run (one click)

Double-click **`Start Dashboard.bat`**.

It starts the dashboard server using the bundled runtime and opens
`http://localhost:3001` in your default browser. If the dashboard is already
running, it just opens the browser tab.

To stop the server: double-click **`Stop Dashboard.bat`** (only stops THIS
dashboard, never other Node processes).

## How to move it to another PC

Option A — copy the whole folder to a USB drive / network share / other PC.

Option B — double-click **`Make Portable Copy.bat`** to create a clean copy
with only the required files (~700 MB, excludes source Excel and build scripts).

## What's inside (required at runtime)

| Item | Purpose |
|---|---|
| `Start Dashboard.bat` | The one-click launcher |
| `runtime\node.exe` | Bundled portable Node.js v25 (self-contained) |
| `server.js` | Dashboard API server (port 3001) |
| `index.html`, `app.js` | The dashboard UI |
| `pl_detail.db` | P&L SQLite database (read-only, ~512 MB) |
| `node_modules\` | better-sqlite3 (pre-compiled for the bundled Node) |
| `api_data\` | JSON fallback cache if the DB is unavailable |

## NOT needed at runtime (safe to leave behind)

- `PL 2022~2026.xlsb` — source workbook (data already ingested into the DB)
- `*.py` — one-time data ingestion/build scripts
- `.playwright-cli\`, `output\` — dev/test artifacts
- `pl_data.json` — build artifact, not read by the server

## Notes & troubleshooting

- **Port**: the dashboard uses port 3001. If another app uses it, set a
  different port before starting: `set PORT=3005` then run the bat (or edit it).
- **Bundled runtime missing?** The launcher falls back to an installed
  Node.js automatically. The bundled `node.exe` must be v25.x — the
  pre-compiled database driver (`better_sqlite3.node`, ABI 141) is tied to it.
  If you ever replace the runtime with a different major version, reinstall
  dependencies on a PC with internet: `runtime\node.exe npm install` (or `npm rebuild`).
- **Firewall prompt**: the server listens on localhost only; allowing or
  blocking the prompt does not affect local use.
- **ARM64 Windows**: works via Windows' built-in x64 emulation.
