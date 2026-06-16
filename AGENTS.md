# AGENTS.md — Mandatory Shared Protocol for All AI Agents

> **This is the single source of truth for every AI agent working on this
> project — Claude Code, OpenAI Codex, DeepSeek, and any other.**
> It is the contract that keeps us all synced. It is read automatically by
> Codex (`AGENTS.md`) and by Claude Code (via `CLAUDE.md`, which points here).

---

## 🛑 THE RULES (read before you touch anything)

These are **mandatory**. Following them is what keeps multiple agents from
overwriting each other and breaking the project.

1. **READ FIRST.** Before doing ANY work, read this entire file,
   [`ARCHITECTURE.md`](ARCHITECTURE.md) (the layer/workflow map + where code goes)
   and [`ROADMAP.md`](ROADMAP.md). They tell you what the project is and what to do.
2. **CLAIM YOUR WORK.** Before starting, add your task to the **Task Board**
   (move it to *In Progress* with your agent name). If another agent already
   owns it, pick something else or coordinate — do not work on the same file at
   the same time.
3. **LOG WHEN YOU FINISH.** Before you end your session / hand off, add a new
   entry at the TOP of the **Work Journal** describing what you did, why, the
   current status, and what should happen next. **A task is not "done" until the
   journal is updated.**
4. **DON'T BREAK THE BUILD.** All tests must pass before you push:
   - `npm test` — dashboard (syntax check + smoke test)
   - `node test_i18n_coverage.js` — Arabic deep-translation coverage (i18n.js)
   - `python3 -m extractor.test_extractor` — extraction engine
   - `python3 -m extractor.test_excel_com` — Excel COM helpers/extractor (mocked, runs on Linux)
   - `python3 -m extractor.test_arabic` — Arabic text/number normalization core
   - `python3 test_db_schema.py` — schema compatibility (seed/mapper/COM all match schema.sql)
   - `python3 test_map_raw_to_db.py` — raw-to-database mapper (includes post-load validation)
   - `python3 test_import_workspace.py` + `python3 test_phase2_integration.py` — Phase 2 import workspace
   - `python3 test_mapping_tool.py` — mapping review tool
   - `python3 test_mapping_tool.py` — mapping review tool (auto-suggest + HTML review report)
   - `python3 -m reports.test_reports` — reports engine
   - `python3 -m reports.test_render` — Excel/PDF rendering
   - `python3 -m reports.test_scenario` — what-if scenarios
   - `python3 -m brain.test_brain` — knowledge engine
   - `python3 -m brain.cli --check` — knowledge link validation
   - `python3 test_project_structure.py` — repo structure guard (root stays clean)
   - `python3 -m mcp_server.test_mcp` — MCP server tools + JSON-RPC dispatch
   If you can't run a test, say so explicitly in your journal entry.
5. **NEVER COMMIT CLIENT DATA.** Real financial files (`intake/`) and their
   captures (`raw/`) are private and git-ignored. Never commit them, paste their
   contents, or send them to any external service.
6. **STAY IN YOUR LANE ON BRANCHES.** Use a feature branch named
   `<agent>/<short-task>` (e.g. `codex/ocr-stage`, `claude/reports-engine`).
   Do not push to another agent's branch. Do not force-push shared history.
7. **SMALL, REVERSIBLE STEPS.** Prefer additive changes. If you must change
   something load-bearing (the DB schema, the server API, the raw-JSON
   envelope), flag it loudly in your journal entry because it affects everyone.

---

## 0. Quick start — exactly what to do (every agent, every task)

Follow these steps in order. Don't skip.

1. **Read** this file, then [`ARCHITECTURE.md`](ARCHITECTURE.md) (the 5 layers +
   the one-way dependency rule + *where code goes*), then [`ROADMAP.md`](ROADMAP.md).
2. **Claim** your task on the [Task Board](#task-board) (move it to *In Progress*
   with your agent name). If someone owns it, pick something else.
3. **Branch:** `git checkout -b <agent>/<short-task>` (e.g. `claude/pdf-fonts`).
   Never push to `main` or another agent's branch.
4. **Locate the layer** in `ARCHITECTURE.md` and put your change *there*, behind
   its existing contract. New code never lands at the repo root (the structure
   guard will fail) — use the layer package or `scripts/`. Reuse the one source
   of truth (schema → `schema.sql`; UI strings → `i18n.js`; COM → `extractor/com_utils.py`).
5. **Explore safely if unsure:** the read-only MCP server (`mcp_server/`) can
   show you the DB (`db_overview`, `run_select`), what extractors are available,
   and the knowledge wiki — without guessing.
6. **Implement + add/extend tests** next to the code you touched.
7. **Run the full test gate** (the list in rule 4). All green, or don't push.
8. **Update docs** you affected, and **add a Work Journal entry at the top**
   (template below). A task is *not done* until the journal is updated.
9. **Open a PR to `main`**; merge only when CI is green.

> **Where is the truth?** `ARCHITECTURE.md` = structure & where code goes ·
> this file = the rules & history · `ROADMAP.md` = product vision ·
> `Agent.md` = technical lessons · `docs/` = reference · `docs/README.md` = index.

### Definition of Done (every PR — keep the docs alive)
A change is done **only** when all of these are true:
- [ ] The full **test gate** (rule 4) is green; new behaviour has a test.
- [ ] **Docs updated in the same PR** — this is mandatory, every time:
  - `ARCHITECTURE.md` if a layer/boundary/where-code-goes changed;
  - `ROADMAP.md` stage status if a stage moved;
  - the relevant `README.md` (root or the package's) for new commands/files;
  - new technical gotchas → `Agent.md`.
- [ ] **Task Board** updated (your row moved to *Done*; new follow-ups added to Backlog).
- [ ] A **Work Journal** entry at the top (template above).
- [ ] No stale references (moved/renamed files) and all internal doc links resolve.

---

## 1. What this project is (so you understand it like the rest of us)

A platform that takes a company's **messy files → clean data → a management
dashboard → a knowledge base → an AI assistant**. Built in stages; each stage is
useful on its own. The full vision and staged plan live in
[`ROADMAP.md`](ROADMAP.md) — **read it.**

### Current architecture (what exists today)

> 📐 **Canonical map: [`ARCHITECTURE.md`](ARCHITECTURE.md)** — the five layers,
> how data flows, the one-way dependency rule, and where new code goes. The
> sketch below is a quick orientation; `ARCHITECTURE.md` is the source of truth.

```
intake/ (messy files)
   │
   ▼  extractor/  ── Stage 1: faithful capture to JSON ──►  raw/*.raw.json + manifest.jsonl
   │
   ▼  map_raw_to_db.py + mapping JSON ──► typed ledger records
   │
pl_detail.db (SQLite ledger)
   │
   ├─► server.js  ── live parameterized SQLite queries, JSON API ──►  index.html + app.js (dashboard)
   ├─► reports/   ── JSON/CSV/XLSX/PDF reports, board packs, scenarios
   └─► brain/     ── linked knowledge base + data-generated notes
```

| Area | Files | Notes |
|------|-------|-------|
| Dashboard server | `server.js` | Node `http`, ONE dependency (`better-sqlite3`), read-only SQLite, dynamic metadata, CSP, optional access token, reports API. |
| Dashboard UI | `index.html`, `app.js` | Vanilla JS + Chart.js, lazy-loaded tabs, client cache. |
| Database schema | `schema.sql` | Canonical table + indexes + views (single source of truth). |
| Schema applier | `db_schema.py` | Applies `schema.sql` for **all** build paths (seed/mapper/COM) — no drift. |
| Dev/test data | `seed_db.py` | Deterministic **synthetic** `pl_detail.db` — runs anywhere, no Excel. |
| Production ingest | `ingest_sheet1.py` | Windows + Excel COM, real `.xlsb` (790K rows). Not the dev path. |
| Agent tools (MCP) | `mcp_server/` | Read-only MCP server: DB / extraction / wiki tools. See `mcp_server/README.md`. |
| **Extraction engine** | `extractor/` | **Stage 1**: messy files → raw JSON. See `extractor/README.md`. |
| Raw-to-DB mapper | `map_raw_to_db.py` | Spreadsheet raw JSON → `pl_detail` via reviewed mapping config. |
| Reports/scenarios | `reports/` | Saved reports, outlook reports, board packs, what-if scenarios. |
| Knowledge base | `brain/`, `knowledge/` | Obsidian-style wiki, graph validation, generated data notes. |
| Tests | `smoke_test.js`, `extractor/test_extractor.py`, mapper/reports/brain tests | Run the relevant suite before pushing. |
| CI | `.github/workflows/ci.yml` | install → seed → dashboard, extractor, mapper, reports, scenario, brain checks. |
| Lessons learned | `Agent.md` | COM gotchas, perf patterns, pitfalls. Worth reading. |

### Run & test it (any platform)

```bash
npm install
pip install -r extractor/requirements.txt -r reports/requirements.txt
python3 seed_db.py --force          # build synthetic dev database
npm start                            # dashboard at http://localhost:3001
npm test                             # dashboard smoke tests
python3 test_project_structure.py    # repo structure guard (root stays clean)
python3 test_db_schema.py            # schema compatibility (all paths == schema.sql)
python3 -m mcp_server.test_mcp       # MCP server tools + JSON-RPC dispatch
python3 -m extractor.cli --list      # show which extractors are available
python3 -m extractor.test_extractor  # extraction engine tests
python3 -m extractor.test_excel_com  # Excel COM helpers/extractor (mocked, no Windows)
python3 -m extractor.test_arabic     # Arabic normalization core tests
python3 test_map_raw_to_db.py        # raw-to-database mapper tests
python3 -m reports.test_reports      # reports engine tests
python3 -m reports.test_render       # Excel/PDF render tests
python3 -m reports.test_scenario     # what-if scenario tests
python3 -m brain.test_brain          # knowledge engine tests
python3 -m brain.cli --check         # validate knowledge links
```

> The authoritative, must-pass gate is the list in **THE RULES → rule 4**; this
> block is the same set with one-line descriptions. CI (`.github/workflows/ci.yml`)
> runs all of it on every push.

### Conventions everyone must follow
- **Keep dependencies minimal.** The server has exactly one (`better-sqlite3`). Justify any new one.
- **Security by default.** Server binds `127.0.0.1`. Use `HOST=0.0.0.0` only for shared deployments,
  and set `ACCESS_TOKEN` to gate requests. Never expose financial data to the open internet
  without auth.
- **No external CDN.** Chart.js is vendored in `chart.umd.min.js`. System fonts only.
  No Google Fonts, no jsDelivr. The dashboard works fully offline.
- **Year/version/outlook are dynamic.** The server reads these from the database at
  startup — do not hard-code year ranges, outlook year, or period cutoffs.
- **The raw-JSON envelope is a shared contract** (`extractor/raw.py`). All
  extractors must produce the same outer shape. Changing it affects every agent.
- **Period encoding:** `period` REAL = `year + period_number/1000`. Versions:
  `Actual`, `T06` (P06 bridge), `T07` (P07–P12 outlook). Don't break these.
- **Do not invent financial metrics** the source ledger can't support (no EBITDA,
  cash flow, or balance-sheet figures from this P&L-only data).
- **Match the existing code style.** Plain, dependency-light, well-commented only
  where a constraint isn't obvious.

---

## 2. The agent team — who is good at what

We are a team with different strengths. Use the right agent for the right job.
(Grounded in research as of June 2026; see Sources at the bottom.)

### Claude Code (Anthropic)
- **Strengths:** fast on filesystem/repo-heavy work, strong codebase
  comprehension and multi-file edits, good at careful refactors, docs, and UX.
  Reads `CLAUDE.md`. Tight MCP/tooling integration.
- **Weaknesses:** runs on Linux containers in this setup — **cannot execute
  Windows-only COM** (Excel/Word/Outlook automation), so it writes that code but
  cannot test it here.
- **Best for:** the dashboard, the engine's cross-platform code, schema/data
  modelling, documentation, code review, anything filesystem-heavy.

### OpenAI Codex (GPT-5.5)
- **Strengths:** top of 2026 agent benchmarks (Terminal-Bench 2.0 ≈ 82.7%);
  excellent at **very long autonomous multi-step tasks** (1,000+ sequential tool
  calls); strong **sandboxed safety**; native `AGENTS.md` + `.codex/skills` +
  MCP; ChatGPT cloud hand-off.
- **Weaknesses:** a bit slower than Claude on filesystem-heavy tasks (IPC
  overhead); no native IDE/GUI; **can spiral into retry loops on flaky tests or
  circular dependencies** — cap turns/tokens on automated runs.
- **Best for:** large, well-specified end-to-end builds that run unattended; jobs
  needing strong sandbox isolation; long test-fix-repeat loops (with caps).

### DeepSeek (V3.2 / V4)
- **Strengths:** very strong **cost-to-performance**; solid reasoning and
  math/programming; efficient long-context via sparse attention; integrates
  reasoning directly into tool-use.
- **Weaknesses:** smaller context window (~131K) than some peers; **less mature
  agent-harness / IDE ecosystem** and no standard agent-file convention, so it
  needs more explicit instruction and tighter task scoping; verify its output
  carefully on complex repo-wide changes.
- **Best for:** well-scoped, self-contained tasks — algorithms, calculations,
  data transforms, report logic, unit tests — where cost efficiency matters and
  the task fits in a clear box. **Always point it at this file first.**

### Suggested division of labour
- **Claude:** dashboard + UI, cross-platform engine code, schema/data mapping,
  docs, reviews.
- **Codex:** big autonomous builds (e.g. the OCR stage, the reports engine),
  long green-the-CI loops, sandbox-sensitive work.
- **DeepSeek:** discrete, well-defined units — a single calculation module, a
  report template, a transform, a batch of tests.
- **Windows-only COM work** (Excel/Word/Outlook automation) must be run/validated
  on a Windows machine with Office by whoever has that environment.

---

## 3. Coordination rules (avoiding collisions)

- **One owner per task.** The Task Board's *In Progress* column shows who owns
  what. Don't touch a file another agent is actively changing.
- **Branch naming:** `<agent>/<short-task>`. Open a PR; don't merge another
  agent's PR without reason.
- **Shared contracts are sacred.** Before changing `schema.sql`, the server API,
  or `extractor/raw.py`, announce it in a journal entry FIRST (these ripple to
  everyone).
- **If you're blocked or unsure, write it in the journal** rather than guessing
  on something load-bearing.
- **Leave the build green.** Never push red tests without a journal note saying
  why and what's needed to fix it.

---

## 4. 📋 TASK BOARD

> Move items between columns and put your agent name on anything you take.

### Backlog — prioritised plan (pick the highest open priority that fits you)

> **How to take one:** read [§0 Quick start](#0-quick-start--exactly-what-to-do),
> move the row to *In Progress* with your name, branch `<agent>/<task>`, satisfy
> the **Done when** line, keep docs current, open a PR. "Suggested owner" is a
> hint by strength (see §2) — not a lock; coordinate if you take another's hint.

| P | Task | Suggested owner | Done when |
|---|------|-----------------|-----------|
| **P0** | **Visual QA pass** — Arabic RTL + English desktop and tablet/mobile in a real browser; screenshot the dashboard; eyeball one Arabic board-pack PDF on a WeasyPrint-enabled box. File issues for anything off. | OpenCode (has Playwright/browser) | Screenshots attached; layout/RTL/number issues logged or confirmed clean. |
| **P0** | **Validate COM on Windows** — run `python3 ingest_sheet1.py --yes` and an `excel_com` extract against real `.xlsx`/`.xlsb` on Windows+Excel; confirm no orphaned `EXCEL.EXE`, password/corrupt files give clean errors. | Owner / any Windows agent | Results recorded in the journal; bugs filed or path confirmed working. |
| **P1** | **Report download UI** — surface report/board-pack generation + download in the dashboard (Stage 2 extend). | OpenCode / Claude (frontend) | Buttons call `/api/reports*`; files download; smoke-tested. |
| **P1** | **Import validation + history in the dashboard** — show Phase 2 `import_history.json` / `validation.json` in the UI. | Codex (built Phase 2 + mapping tool) | A panel lists past imports + their validation status. |
| **P1** | **Mapping tool → guided editor** — turn `mapping_tool.py`'s draft into an operator-reviewable browser step. | Codex | Operator can adjust/confirm a mapping before `map_raw_to_db.py`. |
| **P2** | **Knowledge base extend** — full-text search, HTML/graph viewer, note→report deep links (Stage 4 extend). | DeepSeek / Claude | Search + a viewer work; `brain.cli --check` stays green. |
| **P2** | **Scenarios extend** — multi-scenario compare, scenarios in the live dashboard, volume/price split (Stage 3 extend). | DeepSeek / Claude | New scenario views + tests; zero-adjustment still reproduces baseline. |
| **P2** | **OCR stage for scanned PDFs/photos** — the `pdf-text` extractor already flags image-only pages; add text-recognition + AI + a review step. | Claude (backend) | Scanned fixtures extract to raw JSON with a confidence/review flag + tests. |
| **P2** | **Live Outlook COM** — read a live mailbox / `.pst` (saved `.msg`/`.eml` already work). | Windows agent | New COM extractor mirrors `excel_com` patterns; validated on Windows. |
| **P3** | **`src/` restructure** — the deferred move of core code into layered folders. Guarded migration only (update `server.js` PUBLIC_FILES, `package.json`, CI, `test_project_structure.py` together). | Claude (refactor) | All paths/tests updated in one PR; everything green; ARCHITECTURE.md map updated. |
| **P3** | **Enable PDF + Outlook extractors in CI** — once a clean install path exists (this container's `pdfplumber`/`cryptography` is broken; a normal machine is fine). | any | CI installs the deps and runs those extractor tests. |
| **P3** | **AI agent "Hermes" (Stage 5)** — needs Stages 1–4 mature; can build on the read-only MCP server in `mcp_server/`. | TBD | See ROADMAP; design doc first. |
| **P3** | **Reports engine — client-specific templates** (Stage 2 extend). | Codex / Claude | Per-client template config + a generated example. |

### In Progress (owner)
- _(none currently)_

### Done
- **Excel COM hardening** (Claude Code on `claude/com-extraction-hardening`):
  new shared `extractor/com_utils.py` (dialog-free + macro-disabled session
  with guaranteed cleanup, no-hang `open_workbook`, `find_sheet`, value/error
  cleaning, chunk math); `excel_com.py` refactored to use it with per-sheet
  isolation + formula-error flagging; `ingest_sheet1.py` fixed
  (`UnboundLocalError`, sheet-by-name, `--yes`, ASCII output, indexes only on a
  complete load). 13 mocked tests run COM logic on Linux + CI. COM itself
  unverified here (no Windows) — needs an owner run on Windows + Excel.
- **Phase 2 import-run workspace** (mohamed/minimax-m3 on
  `mohamed/phase-2-import-workspace`): per-client `workspaces/<client>/runs/`
  layout, raw snapshot, automatic db-before.db backup, `import_history.json`
  capped at 50 with prepend-newest, `validation.json` per run, atomic
  rollback CLI. 23 unit tests + 3 integration tests, all green. CLI is
  opt-in via `--client`; legacy behaviour is byte-for-byte equivalent. Plan
  in `.hermes/plans/2026-06-15_150000-phase-2-import-workspace.md`.
- **Arabic Stage 6 documentation + visual QA refresh** (OpenAI Codex on `main`):
  reviewed Arabic desktop/mobile and English desktop in a running browser,
  fixed the initial Arabic page heading and additional dynamic UI translations,
  synced docs with current code, added Arabic PDF render coverage, and aligned
  extractor requirements with the file readers in CI.
- **Arabic PDF rendering** (Stage 6.4b first version): reports use vendored
  Noto Naskh Arabic plus `arabic-reshaper` and `python-bidi` when available;
  Arabic report text is shaped/bidi-corrected for PDF, and render tests create
  Arabic PDF artifacts.
- **Arabic sample seed data**: `python3 seed_db.py --force --locale ar` creates
  an Arabic-dimension demo database while preserving the default English seed.
- **Arabic RTL dashboard** (Stage 6.5 first version): defaults to Arabic
  right-to-left with an EN toggle (falls back to the original LTR layout);
  vendored Cairo font (`cairo.ttf`, served locally); `i18n.js` translates the
  nav/filters/buttons/banner/per-tab titles; digit toggle (Western↔Arabic-Indic);
  charts use Cairo; `[dir="rtl"]` CSS mirrors the explicit left/right rules.
- **Arabic 5b deep UI translation**: `i18n.js` now includes exact Arabic phrase
  translations for section headings, chart titles/subtitles, controls, KPI/table
  labels, empty/loading/status/toast text, risk labels, and report-style notes.
  It applies translations to static HTML plus dynamically inserted DOM text via
  a MutationObserver, while English mode keeps the original layout/text. `app.js`
  also routes canvas-only chart labels/tooltips/axis titles through `tr()` so
  Chart.js legends and tooltips are Arabic too. Tested.
- **Arabic export correctness 4a** (Stage 6.4 part): CSV now writes a UTF-8 BOM
  (`utf-8-sig`) so Excel opens Arabic without mojibake; Excel report sheets are
  flagged right-to-left when content is Arabic (`envelope_has_arabic`). Tests
  added. PDF Arabic (4b) still pending a font decision.
- **Arabic file-format readers** (Stage 6.3 first version): `csv-text` (CSV/TSV,
  stdlib, encoding auto-detect Windows-1256/UTF-8±BOM + delimiter sniff),
  `excel-xlsb` (pyxlsb), `excel-xls` (xlrd) — all emit the shared spreadsheet
  envelope and are registered. CSV/Arabic-encoding + registration tests added.
- **Arabic-aware mapper** (`map_raw_to_db.py`, Stage 6.2 first version): headers
  and sheet names match via `match_key`; numbers parse via `parse_number`; text
  stored cleaned (original spelling kept). Arabic fixture test added. Group-key
  folding for dimensions (6.2b) deferred — needs a schema decision.
- **Arabic normalization core** (`extractor/arabic.py`, Stage 6.1): shared,
  stdlib-only `clean_display` / `match_key` / `parse_number` / `to_ascii_digits`
  / `month_to_number` with the match-key-vs-display-value split. Tested
  (`extractor/test_arabic.py`) + in CI.
- Runnable core (synthetic seed, canonical schema, CI, docs, hygiene).
- Dashboard first-run UX (clear data-not-loaded alert) + non-technical guide.
- Vision & staged roadmap documented.
- Extraction engine Stage 1 foundation (Excel + Word capture, tested).
- **Map raw JSON → database** (`map_raw_to_db.py`): spreadsheet captures load
  into `pl_detail` via a reviewed per-client mapping. Tested + in CI.
- **Reports engine** (`reports/`): eight reports (six core P&L + two
  forecast/outlook) saved from the database as JSON/CSV and **management-ready
  Excel (.xlsx) + PDF**, plus a bundled **board pack** (`--pack`). Supports both
  SQL-backed and computed (`builder`) reports. Tested + in CI.
- **What-if scenarios** (`reports/scenario.py`, Stage 3): apply a reviewable
  JSON of assumption "levers" to the baseline outlook → baseline-vs-scenario
  P&L (JSON/CSV/Excel/PDF). Zero-adjustment = baseline. Tested + in CI.
- **Knowledge base** (`brain/` + `knowledge/`, Stage 4): Obsidian-compatible
  Markdown wiki with a parser/graph (backlinks, orphans, broken-link check, tag
  index, auto index) and region notes generated from the DB. Tested + in CI.
- **Production hardening**: server binds to localhost by default (HOST env override),
  optional ACCESS_TOKEN gate, Chart.js vendored locally, system fonts replace
  Google Fonts, dynamic year/version/outlook metadata from database, fallback
  mode now serves /api/filters and /api/data-freshness. Tested.

---

## 5. 📓 WORK JOURNAL  (newest first — add your entry at the TOP)

> Template for a new entry:
> ```
> ### YYYY-MM-DD — <Agent> — <branch>
> **Did:** what changed (and which files).
> **Why:** the reason / what it enables.
> **Status:** tests passing? anything left half-done?
> **Next:** what the next agent should pick up.
> **Watch out:** gotchas, shared-contract changes, things you couldn't test.
> ```

### 2026-06-16 — Claude Code — main (Guardian: deterministic anomaly detection — "passive guardian")
**Did:** Built the highest-impact idea from Hermes's product brief — turn the
product from passive (you open it and ask) to active (it watches and warns).
- **Engine:** new `reports/anomaly.py` — a deterministic, **source-traceable**
  anomaly detector (no LLM, no network: a finance audience must be able to ask
  "why did you flag this?" and get an explicit rule). Five detectors respecting
  the outlook convention: first-time negative operating profit, gross-margin
  erosion, customer churn, expense-vs-revenue spike (regions), and intra-year
  period spikes (z-score). Each anomaly carries `{year, dimension, label, metric}`
  provenance. Thresholds are explicit module constants (auditable).
- **Tests:** `reports/test_anomaly.py` — one focused crafted ledger per detector
  plus a clean-data test that must stay silent (no false positives). Added to CI.
- **Server:** `/api/anomalies` reuses the engine.
- **Frontend:** new **Guardian** tab (3rd) — severity summary, a list of alerts
  with localized descriptions + a monospace **source trace** line, and an
  "all clear" state. A red **nav badge** shows the alert count, primed on startup
  so the guardian warns without opening the tab. Fully bilingual.
**Why:** "Data alone isn't enough — someone has to watch." This is the feature
that most changes what the product *is*.
**Status:** ✅ Full gate green on EN *and* AR seeds; 6 anomaly unit tests pass;
clean synthetic data correctly yields zero alerts (no false positives); Arabic
phrases verified. New smoke assertions check every anomaly is source-traceable.
**Next:** persist a baseline so spikes compare against history across imports;
optional email/desktop alerting; fold the top anomaly into the Briefing risks.
**Watch out:** `/api/anomalies` spawns Python (primed once on load + on tab
visit). Detectors are tuned for the synthetic distribution — revisit thresholds
(`MARGIN_EROSION_PP`, `CHURN_DROP_FRACTION`, `PERIOD_SPIKE_Z`, …) against real
client data. Deliberately deterministic (not ML/LLM) for auditability + the
no-network runtime constraint.

### 2026-06-16 — Claude Code — main (P2 #7: knowledge-base web integration — Knowledge tab)
**Did:** Brought the "second brain" into the dashboard (audit P2 #7).
- **Brain CLI:** added `--note <id>` to `brain/cli.py` (prints one note as JSON:
  title, body, tags, links) alongside the existing `--search`.
- **Server:** new `/api/wiki/search?q=&limit=` and `/api/wiki/note?id=` endpoints
  that delegate to the tested brain engine. Inputs go through argv (no shell) and
  note ids are dictionary keys (no path traversal) — user input can't reach the
  filesystem unsafely.
- **Frontend:** new "Knowledge" tab — debounced search box → ranked result cards
  (title, snippet, tags) → a note viewer with a small, **escape-first** Markdown
  renderer (headings, bold, code, lists) and clickable `[[wiki-links]]` that load
  the linked note. Bilingual.
- **Tests:** smoke assertions for search/note/404.
**Why:** The knowledge base (definitions, conventions, decisions, processes) was
invisible from the product; now a user can look up "what does this term mean / why
did we decide this" without leaving the dashboard.
**Status:** ✅ Full gate green on EN *and* AR seeds; brain tests + link check pass;
verified search/note/404 live; Arabic phrases resolve.
**Next:** link knowledge notes to specific dashboard reports (deep links), or a
graph view; P2 ingestion (merged cells, OCR).
**Watch out:** The Markdown renderer is intentionally minimal and escapes HTML
first (safe), but it is not a full CommonMark parser — tables/blockquotes/images
render as plain paragraphs. Wiki endpoints spawn Python per call (debounced on the
client).

### 2026-06-16 — Claude Code — main (P2: executive briefing one-pager — decision product)
**Did:** Turned the dashboard from "many views" toward a decision product with a
one-page **Executive Briefing** tab (the client-readiness review's Phase 3 #1).
- **Backend:** new `/api/executive-narrative` composes a briefing from the data
  the outlook already computes (no new P&L logic): a headline (net income / net
  sales / operating profit / gross-margin% vs prior year with direction), the top
  5 product-group movers by Δ operating profit, rule-derived **risks**
  (loss-making groups + revenue at risk, negative-GM groups, customer
  concentration ≥40%, margin compression) with severities, and a **source
  confidence** block (lineage coverage %, validation warnings, row count) reused
  from the import-validation checks.
- **Frontend:** new "Briefing" tab (second, after Overview) — KPI cards, What
  changed / Top risks / Recommended actions / Source confidence sections, all
  composed from structured data via i18n templates (fully Arabic + English,
  verified through `translateText`). A **Print / Save PDF** button with a print
  stylesheet that isolates the briefing → a genuine one-page export with no new
  dependency.
- **Tests:** smoke assertions for `/api/executive-narrative` (headline shape,
  direction enum, arrays, source-confidence overall).
**Why:** Clients prepare recurring management meetings; they want answers (what
changed / what's at risk / what to do / can I trust it), not a tab of charts.
**Status:** ✅ Full gate green on EN *and* AR seeds; verified the endpoint live
(net income +885K, 2 loss-making groups 11.4M at risk, 54% top-5 concentration,
100% lineage). Arabic resolution of every new phrase confirmed.
**Next:** P2 ingestion items (merged-cell/multi-row headers, OCR), or wire the
briefing into a server-rendered PDF board-pack section.
**Watch out:** The briefing is company-wide (ignores the global filters) by design
for v1; risk thresholds (40% concentration, 0.3pp margin) are heuristics in
`getExecutiveNarrative` — tune with a real client. Print export relies on the
`@media print` rules in index.html; re-check if the layout changes.

### 2026-06-16 — Claude Code — main (P1 #4: interactive what-if scenario levers in the dashboard)
**Did:** Made the what-if engine interactive from the browser (audit P1 #4).
- **Backend:** new `/api/scenario-whatif?ns=&cogs=&opex=&tax=&scales=` endpoint
  that builds a scenario config and **reuses the tested Python engine**
  (`reports/scenario.py`) via a new `evaluate_config()` + `--eval-stdin` CLI mode
  — the dashboard never re-implements the P&L math (ARCHITECTURE single-source
  rule). Levers are clamped server-side.
- **Frontend:** a "What-if levers" card on the Scenario tab — sliders for net
  sales / COGS / opex (±30%), a tax-rate slider, and a "COGS scales with revenue"
  toggle. Changes are debounced (250ms) → live baseline-vs-scenario P&L table with
  coloured deltas + a net-income headline. Reset + Export CSV. Fully bilingual.
- **Tests:** new `evaluate_config` unit test (no-op reproduces baseline; a lever
  moves net income) and smoke assertions for the endpoint (flat == baseline,
  positive lever lifts NI).
**Why:** What-if forecasting is only valuable when management can move the levers
themselves; the backend supported it but the UI was static.
**Status:** ✅ Full gate green on EN *and* AR seeds (npm smoke + i18n coverage +
scenario/render/reports/mcp/com/structure). Verified the endpoint live.
**Next:** P2 — executive narrative one-pager (top changes/risks/actions) and
per-row source drill-back from a dashboard figure.
**Watch out:** `/api/scenario-whatif` spawns Python per request (debounced on the
client). Levers are global (no per-dimension `where`) by design for v1; the engine
already supports dimension-scoped adjustments if we want to expose them later.

### 2026-06-16 — Claude Code — main (P1 defensibility: Source & Health tab + COM orphan-kill safety net)
**Did:** Worked the external audit's top actionable items.
- **Source & Health dashboard tab (audit P1 #3).** New `/api/import-health`
  endpoint returns live data-integrity checks (lineage coverage, duplicate grains,
  null critical fields, row counts — computed from the DB) plus per-client import
  history read from `workspaces/<client>/import_history.json`. New dashboard tab
  renders a health summary (passed / warnings / overall), a status-badged checks
  grid, and a run-history table. Fully bilingual (keyed + phrase i18n, Arabic
  provided). A challenged number can now be defended on screen.
- **COM orphan-process safety net (audit P0 #1, partial).** `excel_session()` now
  captures the Excel PID (via `Hwnd`) and **force-terminates** it if `Quit()`
  doesn't take — closing the "orphaned EXCEL.EXE eats memory" risk. New pure
  helpers `_excel_pid` / `_terminate_orphan` are unit-tested for the edge cases.
  ⚠️ A live **Windows** validation sweep with real client files is still required
  (can't run from Linux/CI) — flagged in `Agent.md`.
- **Audit reconciliation:** items #5 (report download UI) and the "System Check"
  env issues are already resolved on `main` (downloads + `setup.sh` from the prior
  P0 push); noted so we don't redo them.
**Why:** Defensibility (where did this number come from, is it clean?) is the
highest-trust gap for a finance client, and orphaned Excel processes are a real
unattended-run risk.
**Status:** ✅ Full gate green on EN *and* AR seeds (npm smoke + i18n coverage +
db/mcp/mapper/phase2/reports/render/scenario/brain/mapping). New smoke assertions
for `/api/import-health`; COM tests 13→15. Verified history rendering with a
simulated workspace manifest, and the empty/synthetic state.
**Next:** P1 #4 — interactive scenario levers in the dashboard; then surface
per-row source drill-back from a dashboard figure.
**Watch out:** `/api/import-health` history reads `workspaces/` (git-ignored,
client data) — empty for the synthetic seed by design. The COM force-kill is
Windows-only/best-effort and untested on real Office; do the Windows sweep before
trusting it in production.

### 2026-06-16 — Claude Code — main (P0 client-readiness: graceful exports + locale-independent tests + one-command setup)
**Did:** Acted on a blunt end-client drive-through of the product and fixed the
three things that broke "it just works":
- **Export 500s → graceful degradation.** `/api/reports/download` for `xlsx`/`pdf`
  now returns a clean `503 {code:"export_unavailable", hint}` when the optional
  Python libs (openpyxl/reportlab) are absent, instead of a raw 500 traceback.
  `/api/reports` advertises an `exportFormats` capability object; the dashboard
  (`app.js`) hides/disables the buttons it can't fulfil with a localized "needs
  setup" tooltip. New `reports.cli --capabilities` (probed + cached by the server)
  is the single source of truth for what's available.
- **Locale-coupled tests fixed.** `smoke_test.js` hard-coded English `region=Africa`
  and failed on the Arabic seed (product *default* is Arabic). It now reads a real
  region from `/api/filters`, so the suite passes on **both** English and Arabic
  seeds. Added a CI step that runs `npm test` against the Arabic seed.
- **One-command setup.** New `setup.sh`: checks prerequisites, installs node +
  optional report deps, seeds a DB, and prints a readiness report (which export
  formats work). README quickstart updated.
**Why:** A clean-install client clicked "PDF" and got a 500, and the flagship
Arabic mode couldn't pass its own smoke test. These are trust-killers before any
feature work matters.
**Status:** ✅ `npm test` passes on EN *and* AR seeds; verified both runtime paths
— deps present → 200 with valid .xlsx/.pdf; deps absent → 503 + disabled buttons.
Structure, reports, render, mcp tests green. New i18n key `Export needs setup`
(Arabic provided), so `test_i18n_coverage.js` stays green.
**Next:** P1 — surface source lineage + import-validation in the dashboard UI so a
challenged number can be defended on screen.
**Watch out:** The server caches export capabilities at first probe; restart after
installing report deps. `setup.sh` installs into the active Python env (no venv) —
fine for the pilot box; revisit if we need isolation.

### 2026-06-16 — Hermes — `5b47c76` → main (full-text search + report downloads + source lineage + MCP harness tools)
**Did:** Landed four backlog items in one push (D17–D20):
- **Full-text search (R5):** new `brain/search.py` — dependency-free weighted
  scoring over the knowledge base; `brain/cli.py` gains `--search`; MCP
  `wiki_search` now delegates to `brain.search`.
- **Report downloads (D18):** `server.js` `/api/reports/download` endpoint serving
  CSV/XLSX/PDF; `app.js` adds three per-report download buttons.
- **Source lineage (D19):** `schema.sql` adds `import_run`, `source_file`,
  `row_lineage` tables + indexes; `seed_db.py` `write_synthetic_lineage` populates
  demo lineage; `map_raw_to_db.py` `iter_records_with_lineage` tracks provenance;
  `reports/validation.py` adds lineage-coverage checks.
- **MCP harness tools (D20):** `project_status`, `run_test`, `brain_check`,
  `task_board_read` added to `mcp_server/tools.py`.
Docs (ARCHITECTURE/ROADMAP/READMEs) and TASK_BOARD updated; R5/R11 marked done.
**Why:** Closes the four highest-ready backlog items — search made the knowledge
base usable, downloads finished the Reports UI, lineage gives every imported row a
verifiable origin, and the harness tools let agents inspect/test the project safely.
**Status:** ✅ All tests passing (`npm test`, `brain`, `test_db_schema`,
`test_map_raw_to_db`, `mcp`). CI run #61 on `main` green. Task Board records
D17–D20 against `5b47c76` (hash backfill `2b38703`).
**Next:** Scenarios in the dashboard (R3), client-specific report templates (R1),
OCR for scanned PDFs (R8).
**Watch out:** `/api/reports/download` PDF/XLSX paths regenerate from the API per
click — fine for 6–9 reports but watch memory on the large Customer P&L.
`row_lineage` is populated synthetically by `seed_db.py` for demo data; real
imports must go through `map_raw_to_db.iter_records_with_lineage` to stay covered.

### 2026-06-16 — Hermes — `hermes/reports-dashboard-ui` (reports download UI)
**Did:** Added the **Reports tab** to the dashboard — the most-repeated "next" from
every recent journal entry. The sidebar now has a "Reports" tab (with document
icon) and a full panel that lists all 6 reports (`yearly_pl`, `regional_pl`,
`product_group_pl`, `country_pl`, `customer_pl`, `yoy_variance`) from the existing
`/api/reports` API with **View** (renders as live table with Export CSV) and
**direct CSV download** buttons per report. Filters auto-disable on the Reports
tab (reports are full-database, not filter-scoped) and re-enable when switching away.
**Why:** The reports engine and API have existed since June 14 but there was
no UI to access them — users had to curl the API or run Python CLI. This closes
the gap and makes every report one click away inside the dashboard.
**Status:** ✅ `npm test` passes. Verified via browser: tab loads, 6 reports
render as cards, "View" fetches and displays a live data table (tested Yearly
P&L: 5 rows × 15 columns), CSV export works, "Back to list" returns, i18n
covers both Arabic and English headings and section text. Filters disable/re-enable
correctly when entering/leaving the tab.
**Next:** A "Report Actions" or "Scenarios" tab that surfaces the what-if
scenario engine in the dashboard; client-specific report templates; OCR stage.
**Watch out:** The reports tab uses `fetchJson` to call `/api/reports/generate`
— report data can be large (Customer P&L has hundreds of rows). Consider adding
a max-row limit or pagination if a single report exceeds ~500 rows. The CSV
download re-fetches from the API rather than using the already-loaded data;
acceptable for 6 reports but worth caching in `requestCache` if reports are
re-visited often. `i18n.js` added two new keys (`reports.sectionTitle`,
`reports.sectionDesc`) — both already have Arabic equivalents.

### 2026-06-16 — Hermes — `hermes/priorities-execution` (sample data + unified reports + MCP tools)
**Did:** Executed the three launch priorities from the audit report.
**Priority Zero (Source Lineage):** Verified that `schema.sql` already has `import_run`, `source_file`, and `row_lineage` tables. `seed_db.py` populates them via `write_synthetic_lineage()`. `map_raw_to_db.py` uses `_register_import_run`, `_source_file_id`, and `_insert_batch_with_lineage` to track every row's origin. **Status: Already implemented.**
**Priority One (Unified Reports):** Added `outlook_pl` and `outlook_monthly` SQL queries to `server.js`, bringing it to 9 reports matching `reports/definitions.py`. Verified via API: `outlook_pl` returns 8 P&L lines with outlook vs prior year variance; `outlook_monthly` returns 12 months (P01-P05 actual, P06-P12 outlook). **Status: Done.**
**Priority Two (MCP Action Tools):** Added 4 new MCP tools: `project_status` (git status, task board, DB presence), `run_test` (allow-listed test commands), `brain_check` (wiki validation), `task_board_read` (read TASK_BOARD.md). All tools are safe, read-only or self-contained. Tests pass (19 tests). **Status: Done.**
**Sample Data:** Created `sample_data/` with Arabic and English CSV samples plus mapping file for testing import workflows.
**Why:** The audit identified three gaps: source lineage (already present but needed verification), report parity between server and Python engine (fixed), and MCP action tools for agent control (added).
**Status:** ✅ All tests pass: `npm test`, `test_db_schema.py`, `test_project_structure.py`, `test_mcp.py` (19 tests), `reports.test_reports`, `brain.test_brain`, `extractor.test_extractor`. API verified via curl.
**Next:** Full-text search for knowledge base (R5), Excel/PDF download from web UI, OCR for scanned PDFs (R8).
**Watch out:** `sample_data/` is tracked in Git as example data. MCP tools are read-only or self-contained; no write access to DB/filesystem. `run_test` uses allow-list only.

### 2026-06-16 — Claude Code — `claude/team-plan-ci` (agent plan + complete the CI gate)
**Did:** Two things for the team. (1) **Closed the CI gate gap** — the Phase 2
`test_import_workspace.py` and `test_phase2_integration.py` existed but weren't
run in CI; added both to `ci.yml` and the rule-4 list, so every test in the repo
now runs on every push. (2) **Rewrote the Task Board into a prioritised,
owner-assigned plan** (P0–P3 table with a suggested owner by strength and a
"Done when" acceptance line for each) so any agent knows exactly what to pick up:
P0 = visual QA (OpenCode) + COM-on-Windows validation; P1 = report download UI,
import validation/history UI, mapping→guided editor (Codex/frontend); P2 =
knowledge/scenarios extend, OCR, live Outlook; P3 = `src/` restructure, PDF/Outlook
in CI, Hermes, client report templates. Added a **Definition of Done** checklist
to §0 that makes "update the docs in the same PR" mandatory (keeps docs alive).
**Why:** Owner asked to continue with what's best for us, plan work for the other
agents, and keep documentation continuously updated. A complete gate + a clear
plan + an enforced DoD is the highest-leverage, lowest-risk move right now.
**Status:** ✅ full gate green locally incl. the two newly-wired Phase 2 suites.
**Next:** agents pick P0/P1 items from the board. I can't do the P0 visual QA
(no browser here) — flagged it for OpenCode.
**Watch out:** "Suggested owner" is a hint, not a lock — coordinate before taking
someone else's hinted task. `i18n.js` still owned by the active translation agent.

### 2026-06-16 — Claude Code — `claude/arabic-pdf-4b` (Arabic PDF 6.4b + font decision)
**Did:** Finished the Arabic PDF substage and locked the font choice.
**Font decision: Noto Naskh Arabic** (OFL, already vendored in `fonts/`) — a
Naskh document face with full Presentation-Forms-A/B coverage (631 + 141 glyphs;
verified it covers every word we render), chosen over Cairo (screen sans) and
Amiri (heavier). Fixed the real gap: the WeasyPrint CSS named `"Noto Naskh
Arabic"`/`"Noto Sans Arabic"` with **no `@font-face`**, so it relied on
system-installed fonts (absent on servers/CI → tofu) and the no-CDN rule. Added
`_arabic_font_css()` that embeds the **vendored TTF** via a `file://` `@font-face`
and pointed both WeasyPrint CSS blocks (single + pack) at it (dropped the
non-vendored "Noto Sans Arabic"). Removed an invalid `wordSpace='RTL'` kwarg
(×2) in the ReportLab styles. Added a `test_arabic_font_css_is_self_contained`
test; confirmed the ReportLab fallback embeds the vendored font (Arabic PDF
renders, 15.7 KB, font embedded). Documented the choice in `ROADMAP.md` and
`reports/README.md`.
**Why:** Owner asked to finish 4b and pick the right font. Noto Naskh is the
correct, safest choice; the missing `@font-face` would have produced broken
Arabic PDFs in any environment without the system font.
**Status:** ✅ render tests pass (reportlab + reshaper + bidi installed here);
WeasyPrint path is the same fix (could not run WeasyPrint here — heavy system
deps — but it's a CSS-level change verified by the self-containment test).
**Next:** if you deploy where WeasyPrint is available, eyeball one Arabic board
pack PDF for layout polish.
**Watch out:** edits are in `reports/render.py` (OpenCode's Arabic PDF area) —
kept surgical (one helper, CSS family swaps, 2 kwarg removals). Both PDF paths
now depend on `fonts/NotoNaskhArabic.ttf` — keep it vendored.

### 2026-06-16 — Claude Code — `claude/i18n-5b-coverage` (Arabic deep content 5b)
**Did:** Completed Stage 6.5b deep-content translation gaps on top of OpenCode's
mechanism (AR_TEXT + regex + MutationObserver). Added a **" · " compositional
fallback** to `translateText` so multi-segment notes (e.g. the profitability
footer "Top N groups by … · X loss-making (…) · Y margin eroding · Z below safe
threshold") translate segment-by-segment instead of leaking English. Added the
missing exact entries (signal labels "Strong growth"/"Growing but margin
eroding", error messages "Database query timed out"/"Chart.js did not load") and
regex rules (the two `gmDrop` signal-action sentences + the footer segments).
New **`test_i18n_coverage.js`** loads `i18n.js` under a stubbed DOM and asserts
the EXACT strings `app.js` renders translate in Arabic (Arabic glyphs present, no
English leakage) and pass through unchanged in English — wired into `ci.yml`,
the rule-4 list, and the structure allow-list.
**Why:** Owner asked to finish 5b. translateText is exported, so coverage is now
verifiable without a browser and protected from regressing.
**Status:** ✅ coverage test + full suite pass.
**Watch out:** Additive to `i18n.js` (OpenCode's layer) — kept changes contained
(appended dict entries, appended regex rules, one fallback block). The page
titles/subtitles already translate via `I18N.t()`; the remaining gaps were the
*dynamic* sentences and the compositional footer. Visual QA on a real browser
still recommended for layout polish.

### 2026-06-15 — Claude Code — `claude/docs-alignment` (documentation alignment)
**Did:** Aligned all the docs so any agent knows exactly what to do. Added an
**§0 Quick start — exactly what to do** to AGENTS.md (9 unambiguous steps:
read → claim → branch → locate the layer → explore via MCP → implement+test →
run the gate → journal → PR) and a "where is the truth?" doc map. Made AGENTS §1
defer to `ARCHITECTURE.md` as the canonical map and refreshed its component table
(added `db_schema.py`, `mcp_server/`) and the run/test block (added structure /
schema / excel_com / mcp tests, with a note that rule 4 is the authoritative
gate). `CLAUDE.md` now points to ARCHITECTURE.md + the MCP server. Fixed stale
references: README no longer lists `precompute_data.py` as a current step (now
flagged archived under `scripts/legacy/`), and the layout table gained
`ARCHITECTURE.md`, `db_schema.py`, `mcp_server/`, `scripts/legacy/`. Marked the
`Agent.md` pre-compute lesson as legacy. Verified every internal doc link
resolves (0 broken).
**Why:** Owner asked to tune all documentation so every agent knows precisely
what to do, and that it stay consistent after today's reorg + MCP work.
**Status:** ✅ docs-only; structure guard + smoke pass; all internal links valid.
Did not rewrite historical journal entries (they are records). `i18n.js` untouched.
**Next:** keep `ARCHITECTURE.md` + this file in sync when layers change (the
quick-start makes that step 8 of every task).

### 2026-06-15 — Hermes / OpenAI Codex — `mohamed/phase-2-import-workspace` → `main` (mapping review tool)
**Did:** Added `mapping_tool.py`, a dependency-light review tool for Phase 2 real-data onboarding. It scans spreadsheet raw JSON captures, extracts sheet headers/sample rows, suggests schema mappings using exact / known bilingual patterns / Arabic normalization / substring matching, writes a reviewable RTL HTML report, and emits a draft `mapping.json`. Added `test_mapping_tool.py` with 15 stdlib `unittest` checks, wired it into CI, added the root structure allow-list entry, and saved the implementation plan in `.hermes/plans/2026-06-15-mapping-review-tool.md`.
**Why:** Phase 2 needed a guided mapping file generator so a second operator can repeat a client import without hand-writing JSON from scratch.
**Status:** Local mapping-tool tests pass; full suite was run before push. No new runtime dependency.
**Next:** The tool is still operator-reviewed, not a full browser editor. Next useful step is surfacing import validation/history in the dashboard UI.
**Watch out:** The generated mapping is intentionally a draft: low-confidence columns are omitted and the operator must review constants/required fields before running `map_raw_to_db.py`.

### 2026-06-15 — Claude Code — `claude/mcp-server` (harness layer, phase 2)
**Did:** Built the **MCP server** (`mcp_server/`) — the harness bridge from
ARCHITECTURE.md §4. Dependency-free (Python stdlib only): speaks MCP over stdio
(newline-delimited JSON-RPC 2.0). Exposes six **read-only** tools across the
layers: `db_overview`, `run_select` (guarded single SELECT, writes/PRAGMA/ATTACH
rejected, opened read-only, row-capped), `pl_summary`, `extractor_availability`,
`wiki_search`, `wiki_get` (path-traversal-safe). Tool logic is pure
(`tools.py`); transport (`server.py`) is a thin wrapper; 17 tests
(`test_mcp.py`) cover tools + the JSON-RPC dispatch using a throwaway DB and the
real wiki. Shipped `.mcp.json` (project-scoped, so Claude Code discovers it) +
`mcp_server/README.md`. Verified an end-to-end stdio round-trip
(initialize/tools/list/tools/call all correct; notification correctly silent).
Wired the test into `ci.yml` + the rule-4 list; marked MCP "built" in
ARCHITECTURE.md; added `mcp_server` to the structure guard's documented packages.
**Why:** Owner approved building a real MCP server so agents can query the DB /
check extraction / search the wiki via safe tools. Stdlib (not the `mcp` SDK,
which wouldn't install cleanly here) keeps the no-extra-deps rule and works offline.
**Status:** ✅ all suites pass incl. the 17 MCP tests; live stdio round-trip OK.
**Next:** optionally add write/action tools later (would need an explicit,
guarded design — today everything is read-only by rule).
**Watch out:** launch the server from the repo ROOT (it imports `db_schema`,
`extractor`, and reads `pl_detail.db`/`knowledge/`). Read-only by design — keep
it that way unless a write tool is deliberately designed. `i18n.js` untouched.

### 2026-06-15 — Claude Code — `claude/project-governance` (organisation + governance, phase 1)
**Did:** Brought order to a 48-file root. Added **`ARCHITECTURE.md`** — the
authoritative 5-layer map (extraction → data → presentation → second brain →
harness), the data-flow workflow, the one-way dependency rule, a directory map,
and the rules for where new code goes. Moved 9 superseded/orphan scripts to
**`scripts/legacy/`** (with a README of what replaced each) and 5 secondary docs
to **`docs/`** (+ `docs/README.md` index; the old `SKILL.md` pre-compute
walkthrough archived to `docs/legacy/` with a banner). Added
**`test_project_structure.py`** — a CI guardrail that fails on stray root
scripts or a package missing its README, so the root can't rot back. Fixed doc
references (README, Agent.md). Wired the guard into `ci.yml` + the rule-4 test
list, and pointed rule 1 at `ARCHITECTURE.md`.
**Why:** Owner asked for a precise, professional organisation with a clear
workflow across all layers, plus protection so growth doesn't turn into
spaghetti. Chose **safe** reorg (no core-code moves) given other agents are
active; full `src/` restructure was explicitly deferred as higher-risk.
**Status:** ✅ all suites pass incl. the new structure guard; no functional code
moved (only legacy scripts + docs), so imports/CI/paths are unaffected.
**Next:** **Phase 2 — build the MCP server** (`mcp_server/`) so agents can query
the DB / check extraction / search the wiki via safe read-only tools (owner
approved). Later, optionally, the guarded `src/` migration.
**Watch out:** `test_project_structure.py` enforces a root allow-list — a NEW
canonical root file must be added to the allow-list in the same commit. Did NOT
touch `i18n.js` (another agent owns it). `.bat` launchers + `README-PORTABLE.md`
kept at root on purpose (portable-distribution UX).

### 2026-06-15 — Claude Code — `claude/db-hardening` (DB layer + extraction↔DB compatibility)
**Did:** Analysed the database layer and fixed the main compatibility gap.
New **`db_schema.py`** is the one module that turns `schema.sql` into a live DB
(`apply_table` / `apply_indexes_and_views` / `apply_schema`, column helpers).
**`ingest_sheet1.py` no longer hand-rolls its DDL** — it builds the table +
indexes + views from `schema.sql`, so the Windows COM path now produces a schema
identical to the seed and the mapper (it had drifted: `net_sales_pct_change` +
an extra `gross_margin_pct_change` vs the schema's `net_sales_pct`). The mapper's
`load_schema_columns`/`split_schema_statements` now delegate to `db_schema`
(one parser). Edge cases: NaN/Infinity rejected in the mapper `convert`, dropped
to null+flagged in `com_utils.clean_com_value`, and serialised as null
defensively in `server.js`. New **`test_db_schema.py`** (10 tests, Linux/CI)
guards against future drift; added to `ci.yml` + the rule-4 list. Wrote
**`DATABASE.md`** (analysis + hardening, bilingual).
**Why:** Owner asked to analyse the DB tech, harden edge cases, and make
extraction fully compatible with the database. Centralising on `schema.sql`
guarantees every build path agrees, forever (test-enforced).
**Status:** ✅ all suites pass on Linux incl. the 10 new schema tests; the
schema-construction parts of the COM ingest are exercised in CI without Windows.
The COM *read* itself still needs an owner run on Windows (unchanged from the
COM-hardening round).
**Next:** optionally derive `seed_db.COLUMNS`/`ingest_sheet1.COLUMNS` from
`db_schema.column_names()` (test already guarantees they match); WAL only if a
concurrent-writer scenario appears.
**Watch out:** `schema.sql` is now load-bearing for THREE paths via
`db_schema.py` — change columns/views there and run `test_db_schema.py`. Did NOT
touch `i18n.js` (another agent owns it).

### 2026-06-15 — Claude Code — `claude/com-extraction-hardening` (COM Excel hardening)
**Did:** Hardened the whole Excel COM path. New `extractor/com_utils.py`
centralises the dangerous bits: `excel_session()` (dialog-free, **macros
force-disabled** for untrusted client files, guaranteed `Quit()` +
`CoUninitialize()` so no orphaned EXCEL.EXE), `open_workbook()` (never hangs —
guard password instead of a modal prompt, `UpdateLinks=0`/`Notify=False`, and a
`CorruptLoad=xlExtractData` retry for damaged files), `find_sheet()` (by name
with index fallback — kills the brittle hard-coded `Sheets(2)`), plus pure
`clean_com_value`/`is_cv_error`/`chunk_bounds`/`normalize_block`. Refactored
`excel_com.py` onto it with **per-sheet isolation** (a bad chart sheet no longer
aborts the file) and **formula-error → null + warning**. Fixed real bugs in
`ingest_sheet1.py`: the **`UnboundLocalError`** when COM failed before the loop
(now `total_inserted=0` up front + a `load_succeeded` gate so indexes/views only
build on a complete load), sheet-by-name, a `--yes` flag for unattended runs,
ASCII-safe output (Windows console can't print `✓`/`—`), and fail-fast if the
source workbook is missing. New `extractor/test_excel_com.py` (13 tests) fakes
the COM object model so all this runs in CI on Linux; added it to `ci.yml` and
the rule-4 test list. Updated `Agent.md` COM section.
**Why:** Owner asked to fix/strengthen the COM Excel + COM extraction for
everything. Centralising prevents the same gotchas (orphan processes, password
hangs, hard-coded sheet index) recurring across the four COM scripts.
**Status:** ✅ all suites pass on Linux incl. the 13 new mocked tests; engine
still falls back to openpyxl when COM is unavailable. ⚠️ **The COM code itself
is NOT verified — there is no Windows/Excel here.** Needs an owner run on
Windows: `python3 ingest_sheet1.py --yes` and an engine extract of a real
`.xlsb`, plus a check that no EXCEL.EXE is left running.
**Next:** optional — apply the same `com_utils` patterns to the legacy
`explore_sheet1.py`/`extract_pl_data.py` dev scripts (left untouched this round);
consider adding the Phase 2 `test_import_workspace.py`/`test_phase2_integration.py`
to `ci.yml` (currently not run in CI).
**Watch out:** Pure-Python logic is well tested, but the live COM behaviour
(guard-password classification, `CorruptLoad`, `AutomationSecurity`) depends on
the Excel build and must be confirmed on Windows. Did NOT touch `i18n.js`
(another agent is actively editing it for 5b).

### 2026-06-15 — mohamed (minimax-m3) — `mohamed/phase-2-import-workspace`
**Did:** Added Phase 2 import-run workspace scaffolding: `import_workspace.py`
(directory layout, history persistence with 50-entry cap, backup/promote
helpers, copy-raw-inputs), CLI subcommands in `import_workspace_cli.py`
(history + rollback), and integration into `map_raw_to_db.load` via new
`--client` and `--no-workspace` flags. Added 23 unit tests in
`test_import_workspace.py` and 3 end-to-end tests in `test_phase2_integration.py`.
Updated `.gitignore` (workspaces, *.db.bak, import_history*.json), README
"Import-run workspaces" section, plan saved to
`.hermes/plans/2026-06-15_150000-phase-2-import-workspace.md`.
**Why:** Make the first real client import repeatable and recoverable
(CLIENT_READINESS_REVIEW Phase 2 #1). Each run is now isolated, snapshotted,
auditable, and roll-able-back.
**Status:** ✅ verified locally — `python3 test_import_workspace.py` (23
passed), `python3 test_phase2_integration.py` (3 passed),
`python3 test_map_raw_to_db.py` (existing tests pass — backwards compat
preserved). `node --check` not affected (no server-side changes). Live
import not run against real client data (synthetic only).
**Next:** Source drill-back from dashboard numbers to source rows/files
(Phase 2 #4). Mapping review UI (Phase 2 #2). Visible validation page in the
dashboard UI (Phase 2 #3).
**Watch out:** The `--client` flag is opt-in; the legacy mapper CLI without
it is byte-for-byte equivalent to the previous behaviour. `schema.sql`,
`server.js`, and the raw-JSON envelope are untouched. The new microsecond
suffix in `make_run_id` changed the run-id format; consumers parsing the id
string should use the timestamp prefix only.


### 2026-06-15 — OpenAI Codex — main (Stage 6 docs + visual QA refresh)
**Did:** Reviewed the current `main` only, ran the dashboard with Arabic seed data, checked Arabic desktop/mobile and English desktop in Playwright, fixed the initial Arabic page heading (`app.js`), expanded dynamic Arabic UI translations (`i18n.js`), added Arabic PDF render coverage (`reports/test_render.py`), aligned `extractor/requirements.txt` with the `.xlsb`/`.xls` readers, and updated `README.md`, `GETTING-STARTED.md`, `ROADMAP.md`, `reports/README.md`, `ARABIC_STAGE6_HANDOFF.md`, and this task board/journal to match the current code.
**Why:** The docs still described Arabic PDF/seed/deep translation work as pending even though code had moved forward; browser QA also showed visible English text in Arabic mode.
**Status:** ✅ verified locally: `npm test`, extractor availability, extractor tests, Arabic normalization tests, mapper tests, reports tests, render tests (including Arabic PDF), scenario tests, brain tests, `brain.cli --check`, and `git diff --check` all passed.
**Next:** Deeper browser QA across every tab and dense Arabic board-pack visual review with real report layouts.
**Watch out:** Work was intentionally committed directly on `main` per owner instruction for this pass; future multi-agent work should return to feature branches unless owner repeats the direct-main instruction.

### 2026-06-15 — OpenCode — main (Arabic: remaining translation, seed data, PDF)
**Did:** Executed the ARABIC_STAGE6_HANDOFF.md plan: (1) covered remaining untranslated dynamic labels — KPI card sub-strings via `tr()`, signal card labels, trend KPI captions, and `translateText()` regex rules for dynamic phrases; (2) added Arabic sample seed data to `seed_db.py` with `--locale ar` flag producing Arabic dimensions (regions, countries, customers, product groups, classes) while preserving English default and financial calculations; (3) downloaded Noto Naskh Arabic variable font (307 KB, OFL) to `fonts/`; (4) implemented Arabic PDF shaping in `reports/render.py` using arabic-reshaper + python-bidi with lazy-loading and graceful degradation — Arabic text is reshaped/bidi-corrected, and the Arabic font is registered and used for all table cells; (5) updated `reports/requirements.txt` and CI workflow for new dependencies; (6) updated `README.md` with `--locale ar` usage and font layout; wrote `ARABIC_STAGE6_HANDOFF.md`.
**Why:** The remaining Arabic work from the handoff plan — finishing translations, Arabic seed data, and PDF rendering — closes the main Arabic Stage 6 items except browser visual QA.
**Status:** ✅ all 8 suites pass on English seed; `python3 seed_db.py --force --locale ar` generates 7,560 Arabic-dimension rows successfully. Arabic PDF test render has the correct font registered and shaping code path available.
**Next:** Browser visual QA for the Arabic RTL dashboard (spacing, overflow, regressions); any remaining visual polish.
**Watch out:** Arabic PDF needs arabic-reshaper + python-bidi at runtime; if absent, fallback to raw unshaped text (graceful degradation). The `fonts/NotoNaskhArabic.ttf` file is 307 KB and must be tracked. `_arabic_shaper()` caches the reshape/bidi functions after first call. Arabic seed command uses `--locale ar`; English default is unchanged.

### 2026-06-15 — OpenCode — main (Arabic 5b deep UI translation)
**Did:** Completed the next 5b pass for Arabic dashboard content: added a broad exact-phrase Arabic translation map in `i18n.js`, translated static inner dashboard text without adding hundreds of `data-i18n` attributes, added a MutationObserver so dynamically rendered table/KPI/status/toast text is translated in Arabic mode, and added `tr()` usage in `app.js` for canvas-only Chart.js labels/tooltips/axis titles. Also fixed `configureCharts()` so it keeps Cairo instead of resetting charts back to system fonts.
**Why:** The main Arabic RTL frame was live, but inner labels (KPI captions, chart titles, table headers, risk labels, empty/loading text, and chart legends/tooltips) still appeared in English. This moves the app closer to Arabic-first operation while preserving English mode.
**Status:** ✅ all suites pass: `npm test`, `extractor.test_arabic`, `extractor.test_extractor`, `test_map_raw_to_db.py`, reports tests, render tests, scenario tests, brain tests, and `brain.cli --check`.
**Next:** Visual QA in a real browser for spacing/overflow in Arabic; Arabic seed/sample display data; PDF Arabic 4b after choosing the report font.
**Watch out:** The translation layer is exact-phrase based. New English UI phrases added later should be added to `AR_TEXT` or routed through `tr()` if they appear inside Chart.js canvases.

### 2026-06-15 — Claude Code — claude/docs-updates-7-files-4bs7ux (Arabic Stage 5 — RTL UI)
**Did:** First version of the full Arabic right-to-left dashboard. Vendored the
Cairo variable font (`cairo.ttf`, 599 KB, OFL, served locally — no CDN; added to
`server.js` PUBLIC_FILES + `.ttf` MIME) and applied it via a `--app-font` CSS
var. New `i18n.js` (loaded before `app.js`): defaults to `lang="ar" dir="rtl"`,
translates every `data-i18n` element (nav, filters, buttons, banner, brand,
sidebar meta), and provides `localizeDigits` + lang/digit toggles (persist in
localStorage, reload to apply). `index.html` now defaults to Arabic RTL with a
`[dir="rtl"]` CSS override block for the explicit left/right rules, and AR/EN +
digit toggle buttons in the topbar. `app.js`: the three number formatters route
through `loc()` (Western↔Arabic-Indic), per-tab titles use `I18N.t(...)`, and
Chart.js defaults to the Cairo font (+ `locale='ar'` in RTL). Added `i18n.js` to
the `npm run check` syntax gate.
**Why:** Owner chose the full RTL Arabic UI. Built it so **English mode = the
original known-good layout** (a safe fallback) and Arabic is the default.
**Status:** ✅ all suites pass; verified live — page serves `dir="rtl"`,
`i18n.js`/`cairo.ttf` serve (200), toggles present, smoke test green. NOTE: could
not visually verify rendering (no headless browser here) — needs an owner look.
**Next:** 5b — translate the deeper content still in English (KPI captions, chart
titles, table headers; many strings scattered in `app.js`), add an Arabic
synthetic dataset to `seed_db.py` for CI-visible RTL testing, and a visual polish
pass (RTL spacing, chart legends/tooltips). Also 4b (Arabic PDF) still pending a
font decision (Cairo may lack PDF presentation forms; Amiri/Noto Naskh safer).
**Watch out:** Toggles reload the page by design (simple, robust). Deep content
is intentionally still English in v1 — the UI will look RTL with Arabic chrome
but English data headings until 5b.

### 2026-06-15 — Claude Code — claude/docs-updates-7-files-4bs7ux (Arabic Stage 4a)
**Did:** Export correctness, part 1. (1) `reports/generate.py` `write_csv` now
uses `utf-8-sig` (UTF-8 BOM) so Excel — especially on Arabic Windows — opens CSV
exports as UTF-8 instead of the local code page, which is what garbles Arabic.
(2) `reports/render.py`: added `_has_arabic` / `envelope_has_arabic` and set
`ws.sheet_view.rightToLeft = True` on Excel report sheets whose content is
Arabic. Added tests: CSV-has-BOM-and-keeps-Arabic (`test_reports.py`) and
Excel-Arabic-is-RTL (`test_render.py`).
**Why:** These are the two exports that were genuinely wrong/uncomfortable for
Arabic. XLSX already stored Arabic fine (it's UTF-8 XML), so only the RTL
orientation was missing; CSV was the real bug.
**Status:** ✅ all suites pass. No new dependencies, no binary assets.
**Next:** 4b — Arabic in PDF board packs. Blocked on a font decision: reportlab
needs an embedded Arabic TTF, and the `arabic-reshaper`+`python-bidi` approach
needs a font that carries Arabic *presentation forms* in its cmap. Cairo (the
chosen UI font) is modern and may render as boxes that way; a traditional face
(Amiri / Noto Naskh) is the reliable PDF choice. Surface to owner before adding
the font binary + deps.
**Watch out:** `envelope_has_arabic` scans headers + cell values for U+0600–06FF;
cheap but runs per sheet — fine at report sizes.

### 2026-06-15 — Claude Code — claude/docs-updates-7-files-4bs7ux (Arabic Stage 3)
**Did:** Added three file-format readers (ROADMAP 6.3), all emitting the shared
spreadsheet envelope so they load through the mapper unchanged:
`extractor/csv_text.py` (CSV/TSV, **pure stdlib**, with encoding auto-detection —
BOM → UTF-8 → Windows-1256 → Latin-1 — and delimiter sniffing; the big Arabic
win, since plain-text exports are where Arabic most often arrives mojibake);
`extractor/excel_xlsb.py` (binary `.xlsb` via optional pyxlsb);
`extractor/excel_xls.py` (legacy `.xls` via optional xlrd). Registered all three
in `registry.py`. Added `test_csv_arabic_encoding` (round-trips a Windows-1256
Arabic CSV and a UTF-8-BOM CSV) and `test_new_extractors_registered` to
`test_extractor.py`; added pyxlsb + xlrd to CI. Also recorded the owner decision
that **6.2b is declined** (keep spellings as typed; don't merge variants).
**Why:** Owner asked for `.xlsb`, `.xls` and CSV support. CSV is the highest
Arabic-encoding risk and is fully testable with no new dependency.
**Status:** ✅ all suites pass; CSV path tested end to end incl. cp1256 decode.
`.xlsb`/`.xls` readers follow the existing optional-dependency pattern; real
binary-format extraction still needs sample files to validate (like COM needs
Windows), so only their registration/availability is asserted in CI for now.
**Next:** Stage 4 — export correctness: CSV written with UTF-8 BOM; PDF board
packs reshaped + bidi-ordered with the embedded Cairo font and RTL tables; XLSX
sheets flagged right-to-left.
**Watch out:** pyxlsb/xlrd return dates as serial numbers (warned in the
capture); date columns will need explicit mapping handling — folded into the
remaining 6.3 fidelity work. `csv-text` claims only `.csv`/`.tsv` (not `.txt`) to
avoid grabbing arbitrary text files.

### 2026-06-15 — Claude Code — claude/docs-updates-7-files-4bs7ux (Arabic Stage 2)
**Did:** Wired the Stage 1 normalization core into `map_raw_to_db.py`. (1) Header
matching now compares `arabic.match_key(...)` instead of exact strings, so a
mapped header matches the sheet header across alef/yaa/taa-marbuta variants,
diacritics, tatweel and stray bidi/format marks. (2) Sheet-name matching uses the
same key. (3) `convert()` now routes TEXT through `clean_display` (keeps the
original spelling, strips invisible junk) and INTEGER/REAL through `parse_number`
(Arabic-Indic digits, ٬/٫ separators, currency, accounting negatives), replacing
the old `_numeric` helper. Added `test_arabic_headers_numbers_and_text` to
`test_map_raw_to_db.py` (Arabic headers with a yaa-variant + RTL mark, Arabic
sheet name with an alef variant, Arabic-Indic numbers, accounting negative).
**Why:** This is where real Arabic client spreadsheets were most likely to fail —
exact header/sheet matching and a numeric parser that choked on Arabic digits and
formats. Now an Arabic capture loads end to end.
**Status:** ✅ all 9 suites pass. The English path is unchanged (existing mapper
tests still pass). Additive behaviour — no schema change.
**Next:** Stage 3 (`.xlsb` via pyxlsb, `.xls` via xlrd, CSV with encoding
detection, merged/multi-row headers). Also **6.2b**: to make spelling variants of
the SAME name total together in reports we need a normalized group-key stored
beside each dimension value — that touches `schema.sql` (load-bearing), so it
must be announced and decided separately before building.
**Watch out:** Text is stored with the client's ORIGINAL spelling (only invisible
junk removed); variant spellings are therefore NOT yet merged in GROUP BY — that
is 6.2b. `match_key` is still display-unsafe; only used here for matching.

### 2026-06-15 — Claude Code — claude/docs-updates-7-files-4bs7ux (Arabic Stage 1)
**Did:** Started the Arabic-first initiative (new ROADMAP Stage 6). Added the
shared normalization core `extractor/arabic.py` (pure stdlib): `clean_display`
(strips bidi/format controls + tatweel, NFC, collapses whitespace, never folds
letters — the value we store/show), `match_key` (folds alef/yaa/taa-marbuta/
hamza variants + diacritics + digits + casefold — used only for matching/
grouping), `parse_number` (Arabic-Indic/Persian digits, ٬/٫ separators, currency
symbols/words, accounting `( )` negatives, Unicode minus), `to_ascii_digits`,
and `month_to_number` (Gregorian month names, Egyptian + Levantine sets).
Added `extractor/test_arabic.py`, wired it into CI and the AGENTS test list,
and claimed the initiative on the Task Board.
**Why:** The project will run mainly on Arabic data. Exact-string header/sheet
matching and the numeric parser break on Arabic spelling variants, digits and
number formats (verified: `أحمد`≠`احمد`, `float('١٬٢٥٠٫٥٠')`/`(1250)`/`ر.س ١٢٥٠`
all throw today). This core is the foundation every later stage builds on.
**Status:** ✅ new suite passes (`python3 -m extractor.test_arabic`); no existing
code changed, so the other 8 suites are unaffected. Pure additive.
**Next:** Stage 2 — integrate into `map_raw_to_db.py`: match headers/sheets via
`match_key`, parse numbers via `parse_number`, add the match-key/display-value
model for dimensions; Arabic golden fixtures. Then Stages 3 (.xlsb/.xls/CSV +
fidelity), 4 (CSV BOM, PDF reshaping+bidi+Cairo font, XLSX RTL), 5 (full RTL UI).
**Watch out:** `match_key` is intentionally LOSSY — only ever use it for matching/
grouping, never store or display it. Folding default is "group variants, show the
original"; revisit if two genuinely distinct names ever collide on one key. The
month table is Gregorian-only by design decision (no Hijri).

### 2026-06-14 — Claude Code — claude/docs-updates-7-files-4bs7ux (code-review fixes)
**Did:** Code-review pass on the production-hardening work; fixed 6 findings.
(1) `server.js` `/api/executive-outlook` `coverage` was hard-coded to
`[1..5]`/`[6..12]`/"P01-P05 + T06 P06 + T07 P07-P12" even though the SQL uses the
dynamic `OUTLOOK_ACTUAL_PERIODS` — now derived from it (`periodRange` helper), so
the labels match the data for any client. (2) `map_raw_to_db.py` post-load
validation now **aborts the swap** on structural problems (no rows, duplicate
grains, nulls in required columns) instead of only printing warnings; P&L
arithmetic drift stays a non-blocking warning. Added a regression test
(`test_post_load_validation_aborts_on_duplicate_grain`). (3) Hard-coded year
defaults in `getPortfolio`/`getDrilldown` (2024/2025) now derive from the live
`VALID_YEARS` (`latestYear`/`priorYear` helpers). (4) Removed dead code
(`OUTLOOK_ACTUAL_MAX`, redundant `!dbAvailable` checks in the reports endpoints).
(5) Access-token comparison is now constant-time (`crypto.timingSafeEqual` via
`tokenMatches`). (6) Unified version string to `4.2`. Updated `README.md` and
`extractor/README.md` to describe the fatal-vs-warning validation behaviour.
**Why:** Three of these (1, 2, 3) were claims the docs now make that the code
didn't actually honour — the dynamic-metadata convention and the "bad load is
caught before the swap" guarantee. The rest are hygiene/security cleanups.
**Status:** ✅ all 8 suites pass — `npm test`, extractor, mapper (incl. new
test), reports, render, scenario, brain, `brain.cli --check` (0 broken links).
Verified live: token auth returns 401/401/200, `/api/executive-outlook`
coverage is computed dynamically, `/api/drilldown` works with no year params.
**Next:** Reports/scenarios download UI in the dashboard; client-specific report
templates; OCR stage.
**Watch out:** Behaviour change — a load with duplicate grains or nulls in
required columns now FAILS (raises `MappingError`) instead of loading with a
warning. This is intentional (the dashboard groups by grain), but any existing
mapping that silently produced such rows will now error until fixed.

### 2026-06-14 — Claude Code — claude/docs-updates-7-files-4bs7ux
**Did:** Updated all project documentation to reflect the production-hardening
work (commit 9aa0a21) across 7 files: `README.md` (security/self-contained
section, env-var examples, `/api/reports` endpoints, `chart.umd.min.js` in the
layout table, dynamic-coverage description, post-load validation), `AGENTS.md`
(security/no-CDN/dynamic-metadata conventions + expanded "Don't Break the Build"
to list all 8 test suites), `ROADMAP.md` (Stage 0 hardening summary, Stage 2
reports API, privacy decision now reflects localhost+ACCESS_TOKEN),
`GETTING-STARTED.md` (offline note, pip + HOST/ACCESS_TOKEN dev examples),
`SKILL.md` (hardening entry in the completion snapshot), `reports/README.md`
(Live API access + Export safety sections), `extractor/README.md` (post-load
validation in the mapper description). Also adding this missing journal entry.
**Why:** The hardening commit changed runtime behaviour (localhost bind, access
token, vendored Chart.js, dynamic metadata, reports API, export safety,
post-load validation) but the docs still described the old state; they're the
first thing every agent and the owner reads.
**Status:** Documentation-only change — no application code touched. Verified
each doc claim against the actual source (server.js HOST/ACCESS_TOKEN/reports
endpoints, vendored Chart.js v4.4.7, `safe_str()` in `reports/__init__.py`,
`_validate_loaded_data()` in `map_raw_to_db.py`, dynamic `OUTLOOK_YEAR`); all 8
listed test suites exist as real files. Did not re-run the suites (no code
changed). The 7-file docs commit was already pushed; this journal entry closes
the protocol gap (the task was never logged).
**Next:** Reports/scenarios download UI in the dashboard; client-specific report
templates; OCR stage.
**Watch out:** The previous OpenCode journal entry (below) actually contains two
merged entries with no header between them — left as-is, not mine to rewrite.

### 2026-06-14 — OpenCode — claude/project-planning-core-8cj4iz (2nd session)
**Did:** Production hardening pass: (1) bind server to 127.0.0.1 by default with HOST env override, (2) add optional ACCESS_TOKEN gate for non-localhost deployments, (3) remove external CDN — vendor Chart.js locally and switch to system fonts, update CSP, (4) make VALID_YEARS and VALID_VERSIONS dynamic from the database at startup, (5) make outlook year detection dynamic instead of hard-coded 2026, (6) add /api/filters and /api/data-freshness to the fallback cache so "limited mode" boot actually works.
**Why:** The public repo had unauthenticated financial endpoints, external CDN script/font dependencies on a private finance dashboard, hard-coded FY2026 logic that would break with a new client/year, and a fallback mode that couldn't complete bootstrap — all blockers for real-client use.
**Status:** ✅ all suites pass (`npm test`, extractor, mapper, reports, render, scenario, brain). Server starts cleanly with dynamic metadata ("Years: 2022,2023,2024,2025,2026 | Versions: Actual,T06,T07 | Outlook year: 2026 (Actual P01-P05)").
**Next:** Commit all changes; then data validation, export safety, reports/scenarios in dashboard.
**Watch out:** Chart.js v4.4.7 is now vendored at `chart.umd.min.js` (205 KB, must be tracked). Changing HOST default from 0.0.0.0 to 127.0.0.1 means remote/LAN access now requires explicit `HOST=0.0.0.0`; documented in the server help text. ACCESS_TOKEN is optional — no token means no auth gate. The KPI cards now use Unicode symbols (↑ $ ◉ ◆ ⚠) instead of Material Icons ligatures; icon appearance is the colored background circle, not the glyph shape.
**Did:** Checked the documentation against the implemented code level and fixed stale completion notes in `AGENTS.md`, `extractor/README.md`, `reports/README.md`, and `SKILL.md`. The docs now reflect that raw spreadsheet JSON mapping, reports/board packs/scenarios, and the knowledge base are implemented and tested, while OCR/live Outlook/Stage 5 remain future work.
**Why:** The public repo had several docs still describing completed work as future work, especially the raw-to-database mapper and the older precomputed-cache architecture.
**Status:** Documentation-only change; no code changed. Verification: `npm test` passed after seeding/installing dependencies; extractor test passed in a temporary venv.
**Next:** If `SKILL.md` is still needed as an active skill, fully rewrite the long legacy sections or remove the file from active references.
**Watch out:** `SKILL.md` remains a legacy deep-dive with historical sections; the top now points contributors to `README.md`, `ROADMAP.md`, and `AGENTS.md` as authoritative.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Built the **knowledge base / "second brain"** (Stage 4): `knowledge/`
holds Obsidian-compatible Markdown notes (`[[wiki-links]]`, `#tags`,
frontmatter — glossary, conventions, reports, data-pipeline, an ADR, plus an
auto-generated index). `brain/` parses them into a graph: backlinks, orphans,
broken-link validation, tag index, JSON graph export, and **region notes
generated from the DB** (`data_notes.py`) that link into the curated wiki.
Added `brain/test_brain.py`; CI now runs the tests AND `brain.cli --check`.
**Why:** A linked company knowledge base where curated knowledge and live
numbers share one space — openable directly in Obsidian.
**Status:** ✅ all suites pass; committed wiki has 0 broken links / 0 orphans.
**Next:** More curated content; full-text search; HTML/graph viewer;
note→report deep links; Stage 5 the AI agent.
**Watch out:** `knowledge/data/` notes are generated from data (may contain
client figures) and are git-ignored — never commit them. Keep curated notes
link-clean so `brain.cli --check` (a CI gate) stays green; no external YAML dep
(minimal frontmatter parser in `parse.py`).

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Built the **what-if scenario engine** (`reports/scenario.py` +
`scenario.example.json`): applies a reviewable JSON of assumption levers
(per-dimension % changes to net sales / COGS / opex, COGS optionally scaling
with revenue, marginal tax rate) to the baseline outlook and produces a
baseline-vs-scenario P&L in JSON/CSV/Excel/PDF. Model is delta-based so a
zero-adjustment scenario reproduces the baseline exactly. Added
`reports/test_scenario.py`; wired into CI; updated README/ROADMAP/Task Board.
**Why:** Stage 3 — let management test a decision before taking it.
**Status:** ✅ all suites pass. Example "Conservative 2026" cuts net income
-21.6% from a -3% revenue move (operating leverage).
**Next:** Multi-scenario comparison; surface scenarios in the live dashboard;
volume/price decomposition; Stage 4 knowledge base.
**Watch out:** Scenario adjusts only net_sales/COGS/opex directly; lines below
operating profit move by identity on the delta (flat marginal tax). Keep
`run_scenario` read-only.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Added **forecast/outlook reports** (`reports/outlook.py`): `outlook_pl`
(full-year outlook = Actual P01-P05 + T06 P06 + T07 P07-P12, vs prior-year
actual, with variance) and `outlook_monthly` (per-month net sales / gross margin
flagged actual vs outlook). Extended the engine to support **computed reports**
via `Report(builder=fn)` returning `(columns, rows[, extra])`; `extra` adds
envelope metadata (e.g. `basis`). Updated tests/README/ROADMAP/Task Board.
**Why:** Forward-looking "where the year is heading vs last year" as saved
reports; rounds out Stage 2 and feeds Stage 3.
**Status:** ✅ all suites pass; outlook figures tie out with the dashboard
(FY2026 outlook $127.7M vs FY2025 $120.3M, +6.2%).
**Next:** Stage 3 what-if scenarios; client-specific templates.
**Watch out:** Outlook treats the LATEST year as the forecast year (stitched
coverage) and falls back to full-year Actual if it has no T06/T07 rows. Builders
must stay read-only.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Added the **board pack** — bundle all reports into one file. Refactored
`reports/render.py` so single reports and bundles share formatting; added
`render_excel_pack` (Contents sheet + a tab per report) and `render_pdf_pack`
(cover page + a section per report). New `generate_board_pack` + `--pack`/`--title`
CLI. Extended `test_render.py`; generated a real 13-page PDF and 7-sheet workbook.
**Why:** A single management-ready artifact to hand to leadership.
**Status:** ✅ all suites pass.
**Next:** Forecast/outlook reports; client-specific templates; Stage 3 scenarios.
**Watch out:** `compute_envelopes` in generate.py is now shared by per-report and
pack paths — keep it pure (no file writes).

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Added **Excel + PDF rendering** to the reports engine (`reports/render.py`):
management-ready `.xlsx` (openpyxl: titled, formatted, real numbers, frozen
header) and `.pdf` (reportlab: landscape, shaded header, right-aligned formatted
numbers). Wired into `reports.cli` (`--format json csv xlsx pdf`) and `generate`.
Added `reports/test_render.py` + `reports/requirements.txt`; CI now installs
reportlab and runs the render test.
**Why:** Stage 2 follow-up — reports ready to hand to management as-is.
**Status:** ✅ all suites pass; generated a real PDF + XLSX from the synthetic DB.
**Next:** Board-pack bundle, forecast/outlook reports, client-specific templates.
**Watch out:** Excel/PDF libs are OPTIONAL and degrade gracefully (missing lib →
clear error, not a crash). reportlab works on normal machines/CI; this dev
container's `cryptography` is broken so `fpdf2`/`pdfplumber` can't load here, but
reportlab does.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Built the **reports engine** (`reports/`): generates six core P&L
reports (yearly, regional, product group, country, customer, YoY variance) as
self-describing JSON + CSV from `pl_detail.db`, reading the Actual-only views in
`schema.sql` so figures tie out with the dashboard. Added `reports/test_reports.py`,
wired into CI, gitignored generated output, updated README/ROADMAP/Task Board.
**Why:** Stage 2 — the "target reports as JSON" the owner asked for: durable,
shareable report artifacts distinct from the live dashboard.
**Status:** ✅ all suites pass (dashboard, extractor, mapper, reports).
**Next:** Client-specific report templates, forecast/outlook reports, a bundled
"board pack"; render to PDF/Excel (done in the entry above).
**Watch out:** Generated reports (`output/reports/`) can contain real client
figures — they're gitignored; keep it that way. To add a report, append to
`reports/definitions.py` only.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Built `map_raw_to_db.py` (+ `mapping.example.json`,
`test_map_raw_to_db.py`): loads extractor spreadsheet raw JSON into `pl_detail`
via a reviewable per-client mapping. Column types come from `schema.sql`; strict
validation of required `year`/`version`/`period` fields and the
`year + period_number/1000` encoding; constants (e.g. `currency=USD`); bounded
10k-row batches; indexes built after load; temp-file build + integrity check +
atomic replace so a failed load never corrupts the live DB. Updated README, CI,
ROADMAP, Task Board.
**Why:** The recommended next step — captured spreadsheet data now reaches the
dashboard. Proven end to end: messy `.xlsx` → extractor → raw JSON → mapper → DB.
**Status:** ✅ all suites pass (`npm test`, extractor, mapper).
**Next:** Per-client mappings for real workbooks; OCR; map non-spreadsheet
sources (Word/PDF/email) once their target shape is decided.
**Watch out — multi-agent note:** Codex independently built a similar mapper in
its own sandbox (commits d743b9b / 7a5c8de / 8c5604f) but its environment is
network-blocked (HTTP 403) and **never pushed to GitHub** — none of it reached
the repo, no PR exists. This entry's implementation was written fresh on the
GitHub side from Codex's described spec. If Codex's branch is ever pushed,
reconcile the two `map_raw_to_db.py` versions rather than blind-merging.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Created this `AGENTS.md` (shared protocol + agent comparison + task
board + journal) and a `CLAUDE.md` stub pointing here. Researched Codex and
DeepSeek to ground the division-of-labour section.
**Why:** The project now has multiple agents (Claude, Codex, DeepSeek). This is
the mandatory sync document so everyone shares the same understanding and logs
their work.
**Status:** Docs only — no code touched; existing tests unaffected.
**Next:** First real multi-agent task is recommended to be "Map raw JSON →
database" (see Task Board). Any agent: read this file, then ROADMAP.md.
**Watch out:** Keep the raw-JSON envelope and DB schema stable — they're shared
contracts. Don't commit `intake/` or `raw/` data.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Built the **extraction engine** (`extractor/`): a pluggable, COM-first
pipeline that captures messy Excel/Word/PDF/Outlook files into one common
raw-JSON envelope (`raw.py`) plus an append-only audit manifest. Excel
(`excel-openpyxl`) and Word (`word-docx`) tested end-to-end; `excel-com`
(Windows COM, full control, reads `.xlsb`), `pdf-text`, and `outlook-msg`
written with graceful availability checks. Added `extractor/test_extractor.py`,
wired it into CI, gitignored client data.
**Why:** Stage 1 of the roadmap — the keystone that lets us take a real client's
files and turn them into data.
**Status:** ✅ `python3 -m extractor.test_extractor` and `npm test` both pass.
**Next:** Map raw JSON into `pl_detail`; add OCR for scanned docs; validate COM
on Windows.
**Watch out:** COM (`excel_com.py`) is Windows-only and was NOT executed here
(Linux) — needs validation on a Windows machine with Office. The engine must
never crash on a bad file — keep extractors' `is_available()` defensive.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Documented the full **vision & staged roadmap** (`ROADMAP.md`): intake →
database → dashboard → knowledge base → AI agent, built in independent stages.
**Why:** Capture the big picture so every agent (and the owner) shares one plan.
**Status:** Docs only.
**Next:** Execute stages in order; Stage 1 first.

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Improved **first-run experience**: a clear, persistent "couldn't load
data / running in limited mode" banner with a Try-again button
(`index.html`, `app.js`), plus a plain-language `GETTING-STARTED.md` and a
`Create Sample Data.bat` double-click helper for non-technical Windows users.
**Why:** Before, a first-time user with no data saw a cryptic, vanishing error.
**Status:** ✅ tests pass; verified both the working and no-database paths.
**Next:** —

### 2026-06-14 — Claude Code — claude/project-planning-core-8cj4iz
**Did:** Made the project **runnable from a fresh clone**: extracted the DB schema
to `schema.sql`, added `seed_db.py` (deterministic synthetic `pl_detail.db`, no
Excel needed), wrote a real `README.md`, added GitHub Actions CI, and stopped
tracking throwaway QA artifacts.
**Why:** Previously the database could only be built on Windows from a
proprietary Excel file, so nobody could run, test, or build on the project.
**Status:** ✅ `npm test` passes against the synthetic database.
**Next:** Build out the extraction engine (done in a later entry above).
**Watch out:** `runtime/node.exe` (91MB) is intentionally kept for the Windows
"portable" launcher — owner's decision; leave it unless told otherwise.

---

## Sources (agent research, June 2026)
- [OpenAI Codex CLI guide (shareuhack)](https://www.shareuhack.com/en/posts/openai-codex-cli-agent-guide-2026)
- [OpenAI Codex CLI review — pros & cons (vibecoding.gallery)](https://vibecoding.gallery/en/tools/openai-codex-cli/)
- [Top CLI coding agents 2026 (Pinggy)](https://pinggy.io/blog/top_cli_based_ai_coding_agents/)
- [DeepSeek-V3.2 release notes (DeepSeek API docs)](https://api-docs.deepseek.com/news/news251201)
- [DeepSeek V3.2 pricing & benchmarks (OpenRouter)](https://openrouter.ai/deepseek/deepseek-v3.2)
- [DeepSeek V4 context window for agents (DEV)](https://dev.to/o96a/deepseek-v4-finally-a-context-window-built-for-agents-228f)
