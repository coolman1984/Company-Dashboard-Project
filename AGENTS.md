# AGENTS.md — Mandatory Shared Protocol for All AI Agents

> **This is the single source of truth for every AI agent working on this
> project — Claude Code, OpenAI Codex, DeepSeek, and any other.**
> It is the contract that keeps us all synced. It is read automatically by
> Codex (`AGENTS.md`) and by Claude Code (via `CLAUDE.md`, which points here).

---

## 🛑 THE RULES (read before you touch anything)

These are **mandatory**. Following them is what keeps multiple agents from
overwriting each other and breaking the project.

1. **READ FIRST.** Before doing ANY work, read this entire file **and**
   [`ROADMAP.md`](ROADMAP.md). They tell you what the project is and what to do.
2. **CLAIM YOUR WORK.** Before starting, add your task to the **Task Board**
   (move it to *In Progress* with your agent name). If another agent already
   owns it, pick something else or coordinate — do not work on the same file at
   the same time.
3. **LOG WHEN YOU FINISH.** Before you end your session / hand off, add a new
   entry at the TOP of the **Work Journal** describing what you did, why, the
   current status, and what should happen next. **A task is not "done" until the
   journal is updated.**
4. **DON'T BREAK THE BUILD.** All tests must pass before you push:
   `npm test` (dashboard) and `python3 -m extractor.test_extractor` (engine).
   If you can't run a test (e.g. Windows-only COM on a Linux agent), say so
   explicitly in your journal entry.
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
   ▼  (NEXT: map raw JSON into the database — not built yet)
   │
pl_detail.db (SQLite ledger)
   │
   ▼  server.js  ── live parameterized SQLite queries, JSON API ──►  index.html + app.js (dashboard)
```

| Area | Files | Notes |
|------|-------|-------|
| Dashboard server | `server.js` | Node `http`, ONE dependency (`better-sqlite3`), read-only SQLite, CSP + validation. |
| Dashboard UI | `index.html`, `app.js` | Vanilla JS + Chart.js, lazy-loaded tabs, client cache. |
| Database schema | `schema.sql` | Canonical table + indexes + views (single source of truth). |
| Dev/test data | `seed_db.py` | Deterministic **synthetic** `pl_detail.db` — runs anywhere, no Excel. |
| Production ingest | `ingest_sheet1.py` | Windows + Excel COM, real `.xlsb` (790K rows). Not the dev path. |
| **Extraction engine** | `extractor/` | **Stage 1**: messy files → raw JSON. See `extractor/README.md`. |
| Tests | `smoke_test.js`, `extractor/test_extractor.py` | Run both before pushing. |
| CI | `.github/workflows/ci.yml` | install → seed → both test suites, on every push/PR. |
| Lessons learned | `Agent.md` | COM gotchas, perf patterns, pitfalls. Worth reading. |

### Run & test it (any platform)

```bash
npm install
pip install -r extractor/requirements.txt
python3 seed_db.py --force          # build synthetic dev database
npm start                            # dashboard at http://localhost:3001
npm test                             # dashboard smoke tests
python3 -m extractor.cli --list      # show which extractors are available
python3 -m extractor.test_extractor  # extraction engine tests
```

### Conventions everyone must follow
- **Keep dependencies minimal.** The server has exactly one. Justify any new one.
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
