# ARCHITECTURE — the map that keeps this project from becoming spaghetti

> **Read this before adding code.** It defines the layers, how data flows, who
> may depend on whom, where new files go, and the guardrails that protect the
> structure. It is the structural source of truth; `AGENTS.md` is the
> coordination protocol; `ROADMAP.md` is the product vision.

---

## 1. The system in five layers

Data flows **left → right**; control flows **top → down**. Each layer only
talks to its neighbours through a defined contract — never reaches across.

```
                       ┌──────────────────────────────────────────────┐
   CONTROL  (5) HARNESS │  Claude Code / agents, governed by AGENTS.md  │
                        │  + CLAUDE.md, steering via the MCP server     │
                       └───────────────┬──────────────────────────────┘
                                        │ MCP (read-only tools)
   ┌─────────────┐   ┌──────────────┐   ▼   ┌──────────────┐   ┌──────────────────┐
   │ (1) EXTRACT │ ─▶│ (2) DATA     │ ─────▶│ (3) PRESENT  │   │ (4) SECOND BRAIN │
   │ files→JSON  │   │ schema + DB  │       │ server+UI    │   │ wiki + graph     │
   │ →ledger     │   │ (SQLite)     │       │ + reports    │   │ (Obsidian-style) │
   └─────────────┘   └──────────────┘       └──────────────┘   └──────────────────┘
```

| # | Layer | Owns | Lives in | May depend on |
|---|-------|------|----------|---------------|
| 1 | **Extraction** | messy files → faithful raw JSON → typed ledger rows | `extractor/`, `map_raw_to_db.py`, `ingest_sheet1.py`, `import_workspace*.py` | (2) for the schema only |
| 2 | **Data** | the canonical ledger, schema, indexes, views | `schema.sql`, `db_schema.py`, `seed_db.py`, `pl_detail.db` (generated) | nothing (it is the foundation) |
| 3 | **Presentation** | live queries → API → dashboard + reports | `server.js`, `index.html`, `app.js`, `i18n.js`, `reports/` | (2) read-only |
| 4 | **Second brain** | linked knowledge notes + data-derived notes + graph | `knowledge/`, `brain/` | (2) read-only |
| 5 | **Harness/control** | governs the agents; (planned) tool access to 1–4 | `AGENTS.md`, `CLAUDE.md`, `.github/`, `mcp_server/` (planned) | all, read-only |

### Dependency rule (the anti-spaghetti law)
**Arrows only point the way the diagram shows.** The data layer (2) must not
import from extraction/presentation. Presentation (3) and the brain (4) must
only **read** the database — never write it. Extraction (1) is the only writer.
If you find yourself wanting a back-edge, that's a design smell — stop and ask.

---

## 2. The data lifecycle (the workflow)

```
intake/  (client's messy Excel/PDF/Word — never committed)
   │  extractor/  (COM on Windows, else openpyxl/pdfplumber/… cross-platform)
   ▼
raw/*.raw.json  (faithful capture + manifest — the single source of truth, never committed)
   │  map_raw_to_db.py + a reviewed mapping.json   (Arabic-aware parsing, validation)
   ▼
pl_detail.db  (SQLite ledger built from schema.sql via db_schema.py)
   │            ▲                         ▲
   │            │ same schema             │ same schema
   │       seed_db.py (synthetic)    ingest_sheet1.py (Windows COM bulk, 790K rows)
   ▼
server.js  (read-only better-sqlite3, parameterised queries, fallback cache)
   ├─▶ index.html + app.js + i18n.js   (RTL Arabic-first dashboard)
   └─▶ reports/                         (JSON/CSV/XLSX/PDF, board packs, scenarios)

knowledge/  (Markdown wiki) ──parsed by──▶ brain/ ──▶ backlinks, graph, data-notes
```

**Three writers, one schema.** `seed_db.py`, `map_raw_to_db.py` and
`ingest_sheet1.py` all build the database **only** through `db_schema.py`, which
applies `schema.sql`. This is enforced by `test_db_schema.py` — they can never
drift apart. See [`docs/database.md`](docs/database.md).

### Load-bearing contracts (don't break silently)
- **Raw envelope** — every extractor emits the same outer JSON shape
  (`extractor/raw.py`).
- **Schema** — `schema.sql` is the only place columns/indexes/views are defined.
- **Period encoding** — `period` REAL = `year + period_number/1000`.
- **Versions** — `Actual`, `T06` (P06 bridge), `T07` (P07–P12 outlook).
- **No invented metrics** — the ledger is P&L-only (no EBITDA/cash-flow/balance).

---

## 3. Where things live (directory map)

```
/                      core runtime + canonical docs only (kept deliberately small)
  server.js app.js i18n.js index.html      → presentation (3)
  schema.sql db_schema.py seed_db.py        → data (2)
  map_raw_to_db.py ingest_sheet1.py
  import_workspace*.py                      → extraction/load (1)
  test_*.py smoke_test.js                   → tests (mirror the module they cover)
  README CLAUDE AGENTS ROADMAP Agent ARCHITECTURE  → canonical docs / governance
  GETTING-STARTED README-PORTABLE *.bat     → end-user onboarding + Windows launchers
extractor/             extraction engine (1) — one module per file type + COM utils
reports/               reporting engine (3)
brain/ + knowledge/    second brain (4)
docs/                  secondary & reference docs (+ docs/legacy/ for archived)
scripts/legacy/        superseded one-off scripts (kept for history, not in CI)
mcp_server/            (planned) harness tool access (5)
.github/               CI
intake/ raw/ workspaces/ *.db   GENERATED or CLIENT DATA — git-ignored, never committed
```

**Root is intentionally minimal.** New code belongs in the layer's package, not
at the root. Ad-hoc/experimental scripts go in `scripts/`. This is enforced by
`test_project_structure.py` (a root allow-list), so the root can't silently rot
back into 48 files.

---

## 4. The harness / control layer (5)

Today the agents are governed entirely by **documents the harness reads**:
- `CLAUDE.md` (Claude Code) → points to `AGENTS.md`.
- `AGENTS.md` → the mandatory multi-agent protocol: the rules, the **task
  board** (claim before you start), the **work journal** (log when you finish),
  and the **test gate** every change must pass.
- `Agent.md` → technical lessons (COM, performance, pitfalls).

**Built: an MCP server (`mcp_server/`)** so an agent can *act on* the system
through safe, **read-only** tools instead of guessing — `db_overview`,
`run_select` (guarded SELECT), `pl_summary`, `extractor_availability`,
`wiki_search`, `wiki_get`. It speaks MCP over stdio with the Python stdlib only
(no extra dependency); the tool **logic** lives in plain, unit-tested functions
(`mcp_server/tools.py`) and the transport (`server.py`) is a thin wrapper. A
project-scoped `.mcp.json` lets Claude Code discover it. This is the bridge that
lets the harness "see" layers 1–4 directly. See [`mcp_server/README.md`](mcp_server/README.md).

---

## 5. Guardrails (how the structure protects itself)

These run in CI (`.github/workflows/ci.yml`) — green is mandatory before merge:

| Guardrail | Protects |
|-----------|----------|
| `test_db_schema.py` | all three writers match `schema.sql` (no schema drift) |
| `test_project_structure.py` | root stays minimal; every package has a README |
| `test_excel_com.py` | COM logic correct without needing Windows |
| `extractor/test_*` · `test_map_raw_to_db.py` · `reports/test_*` · `brain/test_*` | each layer's behaviour |
| `npm test` (`smoke_test.js`) | the server boots and serves |

### Rules for adding code (keep it professional, keep it small)
1. **Find the layer first.** New work goes in that layer's package, behind its
   existing contract. No new top-level scripts (the structure test will fail).
2. **One source of truth.** Schema → `schema.sql`. UI strings → `i18n.js`. COM →
   `extractor/com_utils.py`. Don't duplicate; extend the canonical place.
3. **Respect the dependency direction** in §1. No back-edges.
4. **Minimal dependencies.** The dashboard server has exactly one
   (`better-sqlite3`). Justify any new dependency and isolate agent/dev tooling
   (e.g. `mcp_server/`) from the runtime.
5. **A change isn't done until:** tests pass, docs are updated, and the
   `AGENTS.md` journal has an entry.

---

## ملخص بالعربي
المشروع **٥ طبقات**: (١) استخراج البيانات، (٢) طبقة البيانات/قاعدة SQLite، (٣) العرض
(الخادم + الداشبورد + التقارير)، (٤) العقل الثاني (الويكي + الـ graph)، و(٥) طبقة
الهارنس اللي بتحكم الـ agents عبر `AGENTS.md`/`CLAUDE.md` و(قريبًا) عبر **MCP server**.

**القانون اللي بيمنع الكود من يبقى سباجتي:** البيانات بتتحرك من الشمال لليمين،
والاعتمادية في اتجاه واحد بس — طبقة البيانات هي الأساس وماتعتمدش على حد، والعرض
والعقل الثاني **بيقروا** القاعدة بس وماينفعش يكتبوا فيها، والاستخراج هو الكاتب الوحيد.
**مصدر واحد للحقيقة** لكل حاجة (الـ schema، نصوص الواجهة، الـ COM)، **الجذر بيفضل
صغير** (اختبار `test_project_structure.py` بيحرسه)، وكل المسارات بتبني القاعدة من
`schema.sql` بس. أي تغيير مايخلصش غير لما الاختبارات تعدّي والتوثيق يتحدّث.
