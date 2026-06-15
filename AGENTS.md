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
   - `python3 -m extractor.test_extractor` — extraction engine
   - `python3 -m extractor.test_excel_com` — Excel COM helpers/extractor (mocked, runs on Linux)
   - `python3 -m extractor.test_arabic` — Arabic text/number normalization core
   - `python3 test_db_schema.py` — schema compatibility (seed/mapper/COM all match schema.sql)
   - `python3 test_map_raw_to_db.py` — raw-to-database mapper (includes post-load validation)
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

## 1. What this project is (so you understand it like the rest of us)

A platform that takes a company's **messy files → clean data → a management
dashboard → a knowledge base → an AI assistant**. Built in stages; each stage is
useful on its own. The full vision and staged plan live in
[`ROADMAP.md`](ROADMAP.md) — **read it.**

### Current architecture (what exists today)

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
| Dev/test data | `seed_db.py` | Deterministic **synthetic** `pl_detail.db` — runs anywhere, no Excel. |
| Production ingest | `ingest_sheet1.py` | Windows + Excel COM, real `.xlsb` (790K rows). Not the dev path. |
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
python3 -m extractor.cli --list      # show which extractors are available
python3 -m extractor.test_extractor  # extraction engine tests
python3 -m extractor.test_arabic     # Arabic normalization core tests
python3 test_map_raw_to_db.py        # raw-to-database mapper tests
python3 -m reports.test_reports      # reports engine tests
python3 -m reports.test_render       # Excel/PDF render tests
python3 -m reports.test_scenario     # what-if scenario tests
python3 -m brain.test_brain          # knowledge engine tests
python3 -m brain.cli --check         # validate knowledge links
```

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

### Backlog (not started)
- **Knowledge base — extend** (Stage 4 first version is Done): more curated
  content, full-text search, HTML/graph viewer, note→report deep links.
- **Scenarios — extend** (Stage 3 first version is Done): multi-scenario
  comparison, scenarios surfaced in the live dashboard, volume/price split.
- **OCR stage for scanned PDFs / photos** — detect image-only pages (the
  `pdf-text` extractor already flags them) and run text-recognition + AI.
- **Validate COM extractors on Windows** — run `excel_com.py` against real
  `.xlsx`/`.xlsb` on a Windows machine with Office; record results.
- **Live Outlook COM** — read a live mailbox / `.pst` (saved `.msg`/`.eml`
  already work cross-platform).
- **Enable PDF + Outlook extractors in CI** — once a clean install path exists
  (this container's `pdfplumber`/`cryptography` is broken; a normal machine is
  fine).
- **AI agent "Hermes" (Stage 5)** — see ROADMAP.
- **Reports engine — extend** (Stage 2 Done): client-specific templates.

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
