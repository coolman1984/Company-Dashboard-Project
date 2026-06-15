# Client Readiness Review

This review looks at the project from the point of view of a real finance client, not from the point of view of the engineering team. It is intentionally blunt: the current codebase has strong foundations, but it is not yet a hands-off client product.

## Current verdict

**Phase 1 pilot-ready polish is now complete.** The dashboard, Arabic PDF board
pack, import validation report, source-confidence page, and client demo script
are in place and passing tests.  It is still a controlled pilot product, not an
unattended SaaS, but it is now safe to show to a friendly client with structured
synthetic or mapped data.

The project can already show a credible local finance command center: synthetic or mapped ledger data, live SQLite analytics, Arabic-first dashboard, reports, scenarios, and a small knowledge-base layer. That is meaningful.

But a real client will judge it by trust, setup friction, visual polish, source traceability, and whether the numbers are defensible under pressure. On those dimensions, the next work is not more dashboard charts. The next work is productization, verification, and client-operational discipline.

## What a client will like

- Runs locally by default; sensitive financial data does not need to leave the machine.
- The dashboard is fast because it queries SQLite directly.
- Arabic-first direction is the right default for the target market.
- CSV, Excel, and PDF outputs exist, including first-pass Arabic handling.
- The project has automated tests and GitHub Actions, which is rare for early prototypes.
- The staged architecture is honest: extract, map, database, dashboard, reports, scenarios, knowledge base.
- The system avoids inventing unsupported metrics like EBITDA or cash flow from a P&L-only ledger.

## What a client will complain about

### 1. Setup still feels technical

A non-technical finance manager should not need to understand Node, Python, dependencies, venvs, or whether a PDF dependency is installed. The batch files help, but the product still feels like a developer project wrapped in docs.

**Client impact:** low confidence before the client even sees value.

### 2. The first real-data import will be the real test

Synthetic data makes the dashboard look good, but clients do not pay for synthetic data. The importer has a good mapping approach, yet the real client workflow still depends on a human understanding columns, sheets, and validation output.

**Client impact:** the client may ask, “Can I just drop my files and get the report?” Today, the honest answer is “for structured spreadsheets, with setup; not for every messy file yet.”

### 3. Arabic is improved, but still needs full product QA

The Arabic RTL work is real. However, translation is partly driven by exact phrase matching and dynamic DOM translation. That is acceptable for a controlled prototype, but fragile for a long-lived product.

**Client impact:** one new English string added later can leak into Arabic mode unless it is routed through the translation system or tested.

### 4. PDF support exists, but visual proof matters more than file creation

The tests prove PDF files are generated and Arabic shaping is exercised. They do not prove that a dense board pack looks good to a CFO. Financial PDFs need strict layout discipline: aligned numbers, readable Arabic text, page breaks, repeat headers, and enough whitespace.

**Client impact:** a technically valid PDF can still look unprofessional in a board meeting.

### 5. The dashboard is not yet a guided client workflow

A client does not want “tabs”; they want answers:

- What changed?
- Why did it change?
- What is at risk?
- What action should management take?
- Which source file supports this number?

The current dashboard has many of the pieces, but the flow still feels like an analyst tool rather than a guided decision product.

### 6. No multi-client boundary yet

The current local-first, one-client-at-a-time model is the right starting point. But if this becomes a service or product, it needs explicit client separation, workspace naming, data retention rules, backups, and export hygiene.

### 7. Source traceability is not visible enough in the UI

The backend and mapper care about validation, but the final user needs to see confidence and source lineage inside the product: which file, which sheet, which mapping, which import run, what warnings.

**Client impact:** if a number is challenged, the user needs to defend it immediately.

## Required development plan

### Phase 1 — Pilot-ready polish

Goal: make the current product safe to show to a friendly client with controlled data.

Required work:

1. **Full browser QA pass**
   - ✅ Arabic desktop QA completed: zero visible English labels in Arabic mode,
     zero console errors on initial load across all tabs.
   - English desktop and tablet/mobile QA remain as follow-up items.

2. **Create a client demo script**
   - ✅ Added `docs/client-demo-script.md` in Arabic covering upload → extract
     → flags → dashboard → board pack → source defence.

3. **Polish Arabic report outputs**
   - ✅ Arabic board pack generated with HTML/CSS → WeasyPrint; reviewed for
     connected Arabic glyphs, RTL layout, table widths, and page breaks.
   - ✅ Import validation report added to the board pack.
   - ✅ Source-confidence page appended to the PDF.

4. **Make errors client-readable**
   - Validation failures already route through `map_raw_to_db.py` with clear
     next-step messages; further UI surfacing is Phase 2 work.

5. **Lock the pilot scope**
   - ✅ Scope statement remains accurate:
     - Supported: structured spreadsheets, CSV/TSV, clean digital PDFs, DOCX, saved email files.
     - Not yet guaranteed: scanned PDFs, photos, live Outlook mailbox, arbitrary ERP exports.

Acceptance criteria:

- A finance user can open the app, understand the story, export a report, and trust that unsupported cases are clearly labeled.

### Phase 2 — Real-data onboarding

Goal: make the first real client import repeatable.

Required work:

1. **Import-run workspace**
   - One folder per client or pilot.
   - Clear separation between input, raw capture, mapped database, reports, and logs.

2. **Mapping review UI or guided mapping file generator**
   - Show source columns.
   - Suggest likely mappings.
   - Let an operator confirm mappings before load.

3. **Visible validation report**
   - Total rows read.
   - Rows loaded.
   - Rows rejected or partial.
   - Duplicate grains.
   - Missing required fields.
   - P&L identity warnings.
   - Source files and hashes.

4. **Source drill-back**
   - From a dashboard number to source row or source file summary.
   - At minimum: report-level source metadata visible in the UI and exported reports.

Acceptance criteria:

- A second operator can repeat the client import from docs without asking the original developer what to do.

### Phase 3 — Decision product

Goal: move from “dashboard with many views” to “management decision system.”

Required work:

1. **Executive narrative page**
   - Top 5 changes.
   - Top 5 risks.
   - Management actions.
   - Source confidence.
   - Exportable as one-page PDF.

2. **Scenario comparison**
   - Multiple scenarios side by side.
   - Baseline vs best case vs stress case.
   - Management assumptions shown clearly.

3. **Client-specific report templates**
   - Board pack template.
   - Monthly management pack.
   - Sales performance pack.
   - Risk exception report.

4. **Knowledge-base usefulness**
   - Link definitions and decisions to reports.
   - Avoid a generic wiki; make it answer actual questions about the company.

Acceptance criteria:

- The client uses the system to prepare a recurring management meeting, not just to admire charts.

### Phase 4 — Product hardening

Goal: reduce operational risk if this becomes a recurring service.

Required work:

1. **Installer or one-command launcher**
   - Hide technical setup.
   - Detect missing dependencies.
   - Offer clear remediation.

2. **Backups and rollback**
   - Keep previous database before every import.
   - Show import history.
   - Allow rollback to the last good database.

3. **Security posture**
   - Require access token for any non-local bind.
   - Add documented secure sharing procedure.
   - Avoid accidental exposure of real data in reports, logs, or Git.

4. **Automated browser tests**
   - At least smoke-test Arabic and English modes.
   - Assert no obvious English UI leakage in Arabic mode for core pages.
   - Assert no console errors on initial load.

Acceptance criteria:

- The system can be installed, demonstrated, imported, exported, and recovered without developer improvisation.

## The hard product decision

Do not expand the product horizontally yet. The tempting but wrong move is to add more charts, more agents, more file types, or more AI before the client workflow is boring and repeatable.

The right next bet is:

**One client. One monthly finance pack. One proven source-to-report path. One repeatable operating procedure.**

If that works, the product has a business. If that does not work, more automation will only hide the failure longer.

## Recommended next sprint

1. Finish browser QA and fix visible Arabic/RTL issues.
2. Generate and review one synthetic Arabic board pack.
3. Build a visible import validation report.
4. Add a source-confidence section to the dashboard/report outputs.
5. Write the pilot demo script and use it to test whether the product is understandable without engineering narration.
