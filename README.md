# Company Dashboard

> 🤝 **Multiple AI agents work on this project.** Any agent (Claude, Codex,
> DeepSeek, …) MUST read [`AGENTS.md`](AGENTS.md) first and log its work there.
>
> 🗺️ **New here?** [`ARCHITECTURE.md`](ARCHITECTURE.md) is the map — the five
> layers, how data flows, where code goes. [`docs/`](docs/README.md) has the rest.

A profit-and-loss analytics dashboard. A dependency-light Node.js server runs
live, parameterized SQLite queries over a P&L detail ledger and serves a
single-page dashboard (vanilla JS + Chart.js) plus a CFO-grade executive outlook.

- **Backend:** `server.js` — Node's built-in `http`, one dependency
  (`better-sqlite3`), read-only queries against `pl_detail.db`.
- **Frontend:** `index.html` + `app.js` — lazy-loaded tabs, client-side caching,
  self-contained (Chart.js vendored locally, system fonts, no external CDN).
- **Data:** `pl_detail.db` — a SQLite ledger keyed by year, version, period,
  region, country, customer and product group.
- **Security:** server binds `127.0.0.1` by default — no network exposure.
  Optional `ACCESS_TOKEN` env var gates all requests for shared deployments.
  Zero external CDN dependencies (all assets served from the project folder).

## Quick start (any platform)

The production database is built from a proprietary Excel workbook on Windows
and is **not** committed. For development, tests and CI, generate a realistic
synthetic database instead — no Excel, no network, standard library only:

```bash
./setup.sh                   # one command: deps + optional exports + synthetic DB + readiness report
npm start                    # serves http://localhost:3001 (127.0.0.1 only)
```

`setup.sh` installs the Node dependency, the **optional** Excel/PDF export
libraries, builds a synthetic database, and prints which export formats are
available. The dashboard and CSV export work even if the optional libraries are
missing — the UI simply hides the Excel/PDF buttons it cannot fulfil, and the
download API returns a clear "needs setup" response instead of an error.

To do the same steps by hand:

```bash
npm install                 # installs better-sqlite3
pip install -r reports/requirements.txt   # optional: enables Excel/PDF export
python3 seed_db.py --force  # writes a synthetic pl_detail.db
npm start                    # serves http://localhost:3001 (127.0.0.1 only)
```

For an Arabic-language demo database (Arabic regions, countries, customers, product groups):

```bash
python3 seed_db.py --force --locale ar
```

The dashboard defaults to Arabic right-to-left mode with a language toggle for
English and a digit toggle for Western ↔ Arabic-Indic numerals. Arabic exports
are supported in CSV (UTF-8 BOM), Excel (RTL sheets), and PDF.  **Arabic PDFs are
rendered via HTML/CSS → WeasyPrint** for correct connected glyphs, RTL layout,
and professional board-pack typography; the vendored Noto Naskh Arabic font is
used automatically.

Then open <http://localhost:3001>. No internet required after `npm install`.

**Optional env vars for shared/remote access:**

```bash
HOST=0.0.0.0               # listen on all interfaces (not just localhost)
ACCESS_TOKEN=my-secret      # require ?access_token= in every request
PORT=3005 npm start         # use a different port
```

## Testing

`npm test` syntax-checks the server and frontend, then runs an end-to-end smoke
test that boots the server and exercises every API endpoint:

```bash
python3 seed_db.py --force   # ensure a database exists
npm test
```

## Reports and board pack

The `reports/` engine generates JSON, CSV, Excel, and PDF artifacts from
`pl_detail.db`.  Core P&L roll-ups plus outlook, variance, and scenario reports
are available; see `reports/definitions.py` for the full catalogue.

A single board pack can be produced with:

```bash
python3 -m reports.cli --pack --title "حزمة التقارير المالية 2026"
```

This writes `output/reports/board-pack.xlsx` and `board-pack.pdf`.  Arabic PDF
board packs use HTML/CSS → WeasyPrint for proper RTL and connected-Arabic
glyph rendering and include a final **source-confidence / import-validation**
page summarising row counts, null checks, duplicate-grain checks, and coverage.

## Import-run workspaces (Phase 2)

Real client imports are now isolated in per-client workspaces.  When the
mapper is invoked with `--client <id>`, the run is captured in:

```text
workspaces/<client>/
  import_history.json                       (append-only manifest, newest first, capped at 50)
  runs/<run-id>/
    raw/                                    (snapshot of the captures used in this run)
    logs/load.log                           (mirror of the mapper's stdout)
    reports/                                (reserved for per-run exports)
    validation.json                         (post-load validation summary)
    db-before.db                            (previous good database, copied before the swap)
```

The default flow (no `--client` flag) is unchanged — the legacy CLI is fully
backwards compatible.

Common operations:

```bash
# Load with a workspace
python3 map_raw_to_db.py --mapping mapping.acme.json --client acme --force

# View history
python3 import_workspace_cli.py history --client acme
python3 import_workspace_cli.py history --client acme --json

# Roll back to the last good database
python3 import_workspace_cli.py rollback --client acme --db pl_detail.db
```

The rollback subcommand restores the most recent `db-before.db` (the live DB
as it was just before the last successful run) and records the action in the
client's `import_history.json`.  See `import_workspace.py` for the helpers and
`test_phase2_integration.py` for the end-to-end coverage.

## Data model

`pl_detail` is a single wide table (one row per year × version × period ×
region × country × customer × product group). The canonical schema — table,
indexes and analytical views — lives in **`schema.sql`** and is the single
source of truth shared by the seeder and the production ingestion path.

### Conventions the app depends on

- **Period encoding:** `period` is a REAL equal to `year + period_number / 1000`
  (e.g. `2026.001` = FY2026 P01, `2026.012` = P12).
- **Versions:**
  - `Actual` — realised periods
  - `T06` — the single forecast bridge period P06
  - `T07` — the forward outlook periods P07–P12
- **Current-year coverage:** the server detects the outlook year and Actual period
  count from the database at startup (e.g. FY2026 Actual P01–P05 + T06 P06 + T07
  P07–P12 for the synthetic seed). Prior years are full-year Actual (P01–P12).
  The executive outlook stitches these together; never infer EBITDA, cash flow
  or balance-sheet figures from this P&L-only ledger.

## Production data ingestion (Windows only)

The real ledger (~790K rows) is loaded from `PL 2022~2026.xlsb` via Excel COM
automation. This path requires Windows + Excel + `pywin32` and is not needed for
development:

```bash
python ingest_sheet1.py --yes    # Excel COM -> pl_detail.db (schema + indexes + views)
```

If `pl_detail.db` is unavailable at runtime, the server falls back to any
precomputed JSON in `api_data/` for a subset of endpoints. (That cache was built
by the now-archived `scripts/legacy/precompute_data.py`; live SQLite is the
current path.)

## Extraction engine (data intake)

`extractor/` turns messy client files (Excel, Word, digital PDF, Outlook email)
into faithful raw JSON plus an audit manifest — the first stage of the broader
platform (see [ROADMAP.md](ROADMAP.md)). It prefers Windows Office COM for full
control and falls back to cross-platform Python readers everywhere else.

```bash
pip install -r extractor/requirements.txt
python3 -m extractor.cli --list   # show which file types are ready
python3 -m extractor.cli          # capture intake/ -> raw/
```

See [extractor/README.md](extractor/README.md) for the architecture. Client
source files (`intake/`) and their raw captures (`raw/`) are never committed.

### Loading captured data into the dashboard database

`map_raw_to_db.py` turns the extractor's `raw/*.raw.json` into the canonical
`pl_detail` database using a small, reviewable per-client mapping
(see `mapping.example.json`). Because every client's spreadsheet is laid out
differently, the column mapping is configuration, not code.

```bash
# 1. Copy the example and edit it to match the client's columns/sheet:
cp mapping.example.json mapping.myclient.json

# 2. Dry run first — validates and converts everything, writes nothing:
python3 map_raw_to_db.py --mapping mapping.myclient.json --dry-run

# 3. Load for real (build the dashboard database):
python3 map_raw_to_db.py --mapping mapping.myclient.json --force
```

The loader pulls column types from `schema.sql`, validates the required
`year` / `version` / `period` fields (and the `year + period_number/1000`
encoding), inserts in bounded batches, builds indexes after the load, runs an
integrity check plus **post-load data validation**, and only then atomically
swaps the new database in — so a failed load never corrupts an existing
dashboard database. Validation aborts the swap on structural problems (no rows,
duplicate grains, nulls in required columns) and prints a coverage report; P&L
arithmetic drift is surfaced as a non-blocking warning.

## Project layout

For a blunt end-client readiness critique and development plan, see
[`docs/client-readiness-review.md`](docs/client-readiness-review.md).

| Path | Purpose |
|------|---------|
| `server.js` | HTTP server + all `/api/*` endpoints (live SQLite, dynamic metadata) |
| `index.html`, `app.js` | Dashboard UI |
| `chart.umd.min.js` | Vendored Chart.js v4.4.7 (self-contained, no CDN needed) |
| `ARCHITECTURE.md` | **The layer/workflow map + where new code goes — read before adding code** |
| `schema.sql` | Canonical DB schema (table, indexes, views) — single source of truth |
| `db_schema.py` | Applies `schema.sql` for ALL build paths (seed, mapper, COM ingest) |
| `seed_db.py` | Synthetic database generator (dev/test/CI) |
| `smoke_test.js` | End-to-end API smoke test (`npm test`) |
| `reports/` | Reports engine: JSON/CSV/Excel/PDF, Arabic board pack, outlook, scenarios, import validation, source-confidence |
| `mcp_server/` | MCP server: read-only agent tools (DB, extraction, wiki) — see `mcp_server/README.md` |
| `docs/client-demo-script.md` | Arabic pilot demo script |
| `brain/`, `knowledge/` | Knowledge base ("second brain"): Obsidian-style wiki + graph |
| `map_raw_to_db.py` | Load extracted raw JSON into `pl_detail` via a mapping + post-load validation |
| `ingest_sheet1.py` | Production Excel → SQLite ingestion (Windows) |
| `scripts/legacy/` | Archived one-off scripts (superseded — see `scripts/legacy/README.md`) |
| `Start Dashboard.bat` | Windows one-click launcher |
| `fonts/` | Vendored fonts: Cairo (UI), Noto Naskh Arabic (PDF) |
| `docs/arabic-stage6-handoff.md` | Current Arabic Stage 6 state, QA notes, and remaining work |
| `docs/client-readiness-review.md` | Blunt end-client critique and development plan |

## API endpoints

All endpoints are `GET` and return JSON. Common filters: `version`, `year`,
`region`, `country`, `product`, `customer`, `class`.

| Endpoint | Description |
|----------|-------------|
| `/api/status` | Server + backend health |
| `/api/summary` | Row counts and dimensions |
| `/api/filters` | Distinct filter values |
| `/api/data-freshness` | Period coverage per year/version |
| `/api/yearly-pl` | Yearly P&L roll-up |
| `/api/regional-pl`, `/api/country-pl`, `/api/mgroup-pl`, `/api/customer-pl` | Dimensional P&L |
| `/api/yoy-variance` | Year-over-year deltas |
| `/api/scenario-pl` | Actual vs T06/T07 by year |
| `/api/scenario-whatif?ns=&cogs=&opex=&tax=&scales=` | Interactive what-if: baseline vs scenario P&L for live lever changes |
| `/api/executive-outlook` | Reconciled CFO outlook cockpit |
| `/api/executive-narrative` | One-page executive briefing: top changes, risks, actions, source confidence |
| `/api/drilldown` | Variance contributors between two years |
| `/api/top-products`, `/api/portfolio` | Product economics |
| `/api/reports` | List available saved reports (+ `exportFormats` capability flags) |
| `/api/reports/generate?name=` | Generate a saved report as JSON (6 core P&L reports) |
| `/api/reports/download?name=&format=` | Download a report as CSV/XLSX/PDF (clean `503` if an export library is missing) |
| `/api/import-health` | Live data-integrity checks + per-client import-run history (powers the **Source & Health** tab) |
| `/api/wiki/search?q=&limit=` | Full-text knowledge-base search (powers the **Knowledge** tab) |
| `/api/wiki/note?id=` | Fetch one knowledge note (title, body, tags, links) |
