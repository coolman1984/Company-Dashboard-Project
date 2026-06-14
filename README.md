# Company Dashboard

A profit-and-loss analytics dashboard. A dependency-light Node.js server runs
live, parameterized SQLite queries over a P&L detail ledger and serves a
single-page dashboard (vanilla JS + Chart.js) plus a CFO-grade executive outlook.

- **Backend:** `server.js` — Node's built-in `http`, one dependency
  (`better-sqlite3`), read-only queries against `pl_detail.db`.
- **Frontend:** `index.html` + `app.js` — lazy-loaded tabs, client-side caching.
- **Data:** `pl_detail.db` — a SQLite ledger keyed by year, version, period,
  region, country, customer and product group.

## Quick start (any platform)

The production database is built from a proprietary Excel workbook on Windows
and is **not** committed. For development, tests and CI, generate a realistic
synthetic database instead — no Excel, no network, standard library only:

```bash
npm install                 # installs better-sqlite3
python3 seed_db.py --force  # writes a synthetic pl_detail.db
npm start                    # serves http://localhost:3001
```

Then open <http://localhost:3001>.

## Testing

`npm test` syntax-checks the server and frontend, then runs an end-to-end smoke
test that boots the server and exercises every API endpoint:

```bash
python3 seed_db.py --force   # ensure a database exists
npm test
```

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
- **Current-year coverage (FY2026):** Actual P01–P05 + T06 P06 + T07 P07–P12.
  Prior years are full-year Actual (P01–P12). The executive outlook stitches
  these together; never infer EBITDA, cash flow or balance-sheet figures from
  this P&L-only ledger.

## Production data ingestion (Windows only)

The real ledger (~790K rows) is loaded from `PL 2022~2026.xlsb` via Excel COM
automation. This path requires Windows + Excel + `pywin32` and is not needed for
development:

```bash
python ingest_sheet1.py          # Excel COM -> pl_detail.db (schema + indexes + views)
python precompute_data.py        # optional: api_data/*.json fallback cache
```

If `pl_detail.db` is unavailable at runtime, the server falls back to any
precomputed JSON in `api_data/` for a subset of endpoints.

## Project layout

| Path | Purpose |
|------|---------|
| `server.js` | HTTP server + all `/api/*` endpoints (live SQLite) |
| `index.html`, `app.js` | Dashboard UI |
| `schema.sql` | Canonical DB schema (table, indexes, views) |
| `seed_db.py` | Synthetic database generator (dev/test/CI) |
| `smoke_test.js` | End-to-end API smoke test (`npm test`) |
| `ingest_sheet1.py` | Production Excel → SQLite ingestion (Windows) |
| `precompute_data.py` | Builds `api_data/` JSON fallback cache |
| `analysis_cfo.py` | Offline CFO analysis utilities |
| `Start Dashboard.bat` | Windows one-click launcher |

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
| `/api/executive-outlook` | Reconciled CFO outlook cockpit |
| `/api/drilldown` | Variance contributors between two years |
| `/api/top-products`, `/api/portfolio` | Product economics |
