# FEATURES — the one doc that explains every capability

> **If you read three files, read these:**
> 1. [`ARCHITECTURE.md`](ARCHITECTURE.md) — the 5-layer map + dependency rules.
> 2. **this file** — every feature, the tech behind it, when to use it, edge cases.
> 3. [`AGENTS.md`](AGENTS.md) — the multi-agent rules + task board + work journal.
>
> Everything else (`README.md`, `ROADMAP.md`, `Agent.md`, per-package READMEs) is
> reference. You do **not** need to read it to be productive here.

---

## 1. The project in 30 seconds

A **local-first, Arabic-first profit-and-loss analytics product**. A
dependency-light Node server runs live SQLite queries over a P&L ledger and
serves a single-page dashboard plus a set of **decision features** (briefing,
guardian, what-if, sensitivity, ask, knowledge). Sensitive financial data never
leaves the machine: the server binds `127.0.0.1`, vendors all assets, and every
feature is **deterministic and offline** — no LLM, no network calls.

```
 intake/  →  extractor/  →  raw JSON  →  map_raw_to_db.py  →  pl_detail.db (SQLite)
 (client files)            (faithful)    (+ schema.sql)        │
                                                               ▼
                              server.js  ──  /api/*  ──►  index.html + app.js (tabs)
                                  │                          + i18n.js (AR/EN)
                                  └── spawns ──►  reports/*.py feature engines
                              brain/ (knowledge)  ──►  /api/wiki/*
```

See `ARCHITECTURE.md` for the full 5-layer diagram and the dependency law.

---

## 2. The Feature Module Pattern (read this before adding a feature)

**Yes — features are separate small modules that work alone and connect cleanly.**
Every analytical feature follows the same four-part contract, which is what lets
them be developed, tested, and reasoned about independently *and* compose:

```
┌── ENGINE ───────────────┐   ┌── ENDPOINT ──┐   ┌── UI ─────────┐   ┌── STRINGS ──┐
│ reports/<feature>.py     │   │ server.js    │   │ index.html tab │   │ i18n.js     │
│ • pure functions         │──►│ /api/<feature>│──►│ app.js loader  │──►│ AR + EN     │
│ • own CLI (--json)       │   │ thin: spawn  │   │ render()       │   │ keyed+phrase│
│ • own unit tests         │   │ Python, JSON │   │ bilingual      │   │             │
└──────────────────────────┘   └──────────────┘   └───────────────┘   └─────────────┘
        works alone                 the seam            connects             localized
```

Rules that keep modules independent yet composable:

- **The engine is the source of truth.** All maths lives in `reports/<feature>.py`
  as pure functions with a `--json` CLI and `reports/test_<feature>.py`. It must
  run and be tested with **zero** Node involvement.
- **The endpoint is thin.** `server.js` validates/clamps inputs and `spawnSync`s
  the engine (or runs SQL directly for the lightweight ones). No business logic.
- **The UI is one tab.** A `load<Feature>()` in `app.js`, a `<section class="panel">`
  in `index.html`, registered in `tabLoaded` + the loader map. All user text via
  `tr()` / `data-i18n`, with Arabic added to `i18n.js`.
- **Modules compose by reusing engines, never by reaching across layers.**
  Examples already in the tree:
  - `sensitivity.py` **reuses** `scenario.py` (it never re-derives P&L maths).
  - the **Briefing** reuses the anomaly engine (`/api/anomalies`) + the
    import-validation report for its "source confidence" + "guardian flagged".
  - the **Guardian** and **Ask** both reuse `outlook.py` helpers
    (`detect_years`, `_outlook_where`).

**To add a feature:** copy an existing engine (`anomaly.py` is a good template),
write its tests, add a thin endpoint, add a tab, add Arabic strings, wire the
test into `.github/workflows/ci.yml`, and add a row to the catalogue below.
A change isn't done until tests pass on **both** the English and Arabic seed.

---

## 3. Shared conventions every feature depends on

These are load-bearing. Break them and features silently lie.

| Convention | Rule |
|---|---|
| **Period encoding** | `period` REAL = `year + period_number/1000` (`2026.001` = FY2026 P01). Recover the month with `CAST(ROUND((period-CAST(period AS INT))*1000) AS INT)`. |
| **Versions** | `Actual` (realised), `T06` (the P06 bridge), `T07` (P07–P12 outlook). |
| **Outlook year** | The latest year = `Actual P01–P05 + T06 P06 + T07 P07–P12`. Prior years are full-year `Actual`. Use `reports/outlook.py:_outlook_where` / `detect_years`. Within a year, periods never overlap across versions, so summing rows per year+period is safe. |
| **P&L only** | The ledger has no EBITDA / cash-flow / balance-sheet. Never invent them. |
| **One schema** | Columns/indexes/views live only in `schema.sql`; all three writers build through `db_schema.py`. |
| **Offline** | No network, no LLM, no external CDN at runtime. Determinism is a feature (answers must be auditable). |

---

## 4. Feature catalogue

Each entry: **what it does · tech · when to use · edge cases · files/endpoint/tab**.

### 4.1 Executive Briefing  (decision product)
- **What:** a one-page narrative — headline KPIs vs prior year, top product-group
  movers, rule-derived risks + recommended actions, what the guardian flagged,
  and a source-confidence line. Printable to a one-page PDF.
- **Tech:** composed in `server.js` from the outlook query; folds in
  `/api/anomalies` and the `import_validation` report. Deterministic templating
  in `app.js` (bilingual), `@media print` isolates the page.
- **When:** preparing a board/management meeting; the "tell me the story" view.
- **Edge cases:** company-wide (ignores global filters by design); risk
  thresholds (40% concentration, 0.3pp margin) are heuristics — tune per client;
  degrades gracefully if anomaly detection is unavailable.
- **Where:** `getExecutiveNarrative` in `server.js` · `GET /api/executive-narrative`
  · **Briefing** tab (`loadBriefing`/`renderBriefing`).

### 4.2 Guardian — anomaly detection  (passive guardian)
- **What:** watches the ledger and flags the unusual: first-time negative
  operating profit, gross-margin erosion, customer churn, region expense-vs-
  revenue spikes, intra-year period spikes (z-score). Every alert is
  **source-traced** (`year · dimension=label · metric`).
- **Tech:** `reports/anomaly.py` — explicit rules + thresholds (auditable),
  reuses `outlook.py`. A red nav badge is primed on startup.
- **When:** the "what should I worry about?" view; passive monitoring.
- **Edge cases:** thresholds tuned for the synthetic distribution — revisit on
  real data; deterministic (not ML) on purpose so "why was this flagged?" always
  has an answer; clean data correctly produces **zero** alerts (no false positives).
- **Where:** `reports/anomaly.py` (+ `test_anomaly.py`) · `GET /api/anomalies`
  · **Guardian** tab.

### 4.3 What-if scenario levers
- **What:** sliders for net sales / COGS / opex / tax + a "COGS scales with
  revenue" toggle; recomputes a full baseline-vs-scenario P&L live.
- **Tech:** `reports/scenario.py` (`evaluate_config` + `--eval-stdin`). A no-op
  scenario reproduces the baseline exactly (delta-by-identity model).
- **When:** "what happens to profit if …" exploration.
- **Edge cases:** levers are global (no per-dimension `where` in the UI, though
  the engine supports it); spawns Python per change (debounced 250ms client-side).
- **Where:** `reports/scenario.py` · `GET /api/scenario-whatif` · **Scenario** tab.

### 4.4 Profit sensitivity (tornado)
- **What:** ranks which lever moves net income the most (±5% shock each),
  with a tornado chart + table.
- **Tech:** `reports/sensitivity.py` — **reuses `scenario.run_scenario`** (7
  evaluations: baseline + 3 drivers × 2 directions). Pure example of module reuse.
- **When:** "where is profit most exposed?" before a planning cycle.
- **Edge cases:** with `cogs_scales_with_revenue=True`, a net-sales shock is
  damped (COGS moves too) — that is correct, not a bug; shock size is clamped 1–50%.
- **Where:** `reports/sensitivity.py` (+ `test_sensitivity.py`) ·
  `GET /api/sensitivity?delta=` · **Scenario** tab (card under the levers).

### 4.5 Ask — offline natural-language query
- **What:** type a question in Arabic/English ("compare Africa vs Asia net
  sales", "مبيعات أفريقيا 2025"); returns a table and echoes *what it understood*.
- **Tech:** `reports/nlquery.py` — a transparent rule-based parser (metric +
  group-by + entity filters + year + quarter) → parameterised SQL. **No LLM, no
  network.** Entity names matched against the DB's own values.
- **When:** managers who want the answer without writing SQL.
- **Edge cases:** understands documented intents, not arbitrary free text (falls
  back to net_sales + current year); cross-language entity matching is limited to
  the data's own language; extend synonyms in `METRIC_SYNONYMS`/`DIM_SYNONYMS`.
- **Where:** `reports/nlquery.py` (+ `test_nlquery.py`) · `GET /api/nl-query?q=`
  · **Ask** tab.

### 4.6 Reports + exports
- **What:** 9 saved P&L reports as JSON/CSV/XLSX/PDF, plus an Arabic board pack.
- **Tech:** `reports/definitions.py` + `generate.py` + `render.py`. XLSX needs
  `openpyxl`, PDF needs `reportlab`/`weasyprint` — **optional**. The server probes
  capability (`reports.cli --capabilities`) and degrades gracefully.
- **When:** producing artifacts to hand off.
- **Edge cases:** if an export lib is missing, the API returns a clean `503
  {code:"export_unavailable"}` (never a 500) and the UI **hides** that button;
  CSV always works. Run `./setup.sh` to install the optional libs.
- **Where:** `reports/` · `GET /api/reports`, `/api/reports/generate`,
  `/api/reports/download` · **Reports** tab.

### 4.7 Source & Health  (defensibility)
- **What:** live data-integrity checks (lineage coverage, duplicate grains, null
  critical fields, row counts) + per-client import-run history.
- **Tech:** `server.js` reuses the `import_validation` report + reads
  `workspaces/<client>/import_history.json`.
- **When:** "can I trust / defend this number?"; after a client import.
- **Edge cases:** history is empty for the synthetic seed (no client workspace) —
  by design; malformed manifests are skipped, not fatal.
- **Where:** `getExecutive... readImportHistory` in `server.js` ·
  `GET /api/import-health` · **Source & Health** tab.

### 4.8 Knowledge base  (the "second brain")
- **What:** search the company's definitions/conventions/decisions/processes and
  read notes with clickable `[[wiki-links]]`.
- **Tech:** `brain/` (parse + search). The server delegates via argv (no shell;
  note ids are dictionary keys → no path traversal). UI uses an escape-first
  minimal Markdown renderer.
- **When:** "what does this term mean / why did we decide this?"
- **Edge cases:** the Markdown renderer handles headings/bold/code/lists/links
  only (no tables/images); broken links surface a 404 in the viewer.
- **Where:** `brain/` (+ `brain/cli.py --note`) · `GET /api/wiki/search`,
  `/api/wiki/note` · **Knowledge** tab.

### 4.9 Foundational layers (not "tabs", but the ground everything stands on)
- **Data:** `schema.sql` + `db_schema.py` + `seed_db.py` (synthetic dev/CI data;
  `--locale ar` for Arabic). The MCP server (`mcp_server/`) exposes read-only
  tools to agents.
- **Extraction:** `extractor/` (Excel/Word/PDF/email → raw JSON) and
  `map_raw_to_db.py` (raw → ledger, with per-client workspaces + rollback).
  Windows Excel COM logic lives in `extractor/com_utils.py` (`excel_session`
  force-kills orphaned `EXCEL.EXE`; a live Windows sweep is still owed).

---

## 5. Endpoint → engine → tab quick map

| Endpoint | Engine / source | Tab |
|---|---|---|
| `/api/executive-narrative` | `server.js` (+ anomalies, validation) | Briefing |
| `/api/anomalies` | `reports/anomaly.py` | Guardian |
| `/api/scenario-whatif` | `reports/scenario.py` | Scenario |
| `/api/sensitivity` | `reports/sensitivity.py` → `scenario.py` | Scenario |
| `/api/nl-query` | `reports/nlquery.py` | Ask |
| `/api/reports*` | `reports/` (definitions/generate/render) | Reports |
| `/api/import-health` | `server.js` + `import_validation` | Source & Health |
| `/api/wiki/*` | `brain/` | Knowledge |
| `/api/executive-outlook`, `/api/*-pl`, … | `server.js` (live SQL) | Overview/Regional/… |

---

## 6. Gotchas (the short list that saves hours)

- **Two seeds, two truths.** Tests must pass on `seed_db.py --force` *and*
  `--force --locale ar`. The smoke test reads dimension values from `/api/filters`
  rather than hard-coding names — keep it that way.
- **i18n has two channels:** keyed `data-i18n` entries (in `DICT.ar`/`DICT.en`)
  for static markup, and an Arabic **phrase map** consumed by `translateText`
  for strings built dynamically in `app.js`. Dynamic `tr()` strings need a phrase
  entry or they show English in Arabic mode. `translateText` matches **whole**
  trimmed strings — don't add ultra-generic words ("up"/"down") to it.
- **Capabilities are cached.** The server probes export libs once; restart after
  `pip install`.
- **Python-spawning endpoints** (scenario/sensitivity/anomaly/nlquery/wiki) cost a
  process per call — fine locally, debounce on the client for sliders/search.
- **Root stays minimal.** New code goes in a layer package; `test_project_structure.py`
  guards the root. New canonical root docs must be added to its allow-list.
