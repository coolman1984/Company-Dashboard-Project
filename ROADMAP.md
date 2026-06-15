# Project Vision & Roadmap

> The big picture, in plain language. This is the north star for the whole
> project — far bigger than the dashboard alone. We build it in **stages**, and
> **each stage is useful on its own**, so value arrives early and often.

---

## The vision in one sentence

Walk into a company with messy files, turn that mess into clean data, and give
management a living picture of their business — plus a "second brain" that
remembers everything and an AI assistant that runs and improves the work.

---

## How the whole machine fits together

Think of it as an assembly line. Data comes in messy on the left and comes out
as insight, knowledge, and automation on the right:

```
 Messy files            Clean data            Understanding          Brains
 -----------            -----------           --------------         --------
 Excel  ┐                                      Reports  ┐
 PDF    ┼─►  EXTRACT  ─►  DATABASE  ─►  CALCULATE  ─►  Dashboard ┼─►  Wiki ("2nd brain")
 Word   ┘   (+ save raw     (fast,      & QUERY        Scenarios ┘        │
            as JSON)        queryable)                                    ▼
                                                                   AI Agent ("Hermes")
                                                                   runs & improves it all
```

---

## The stages

### ✅ Stage 0 — The dashboard foundation (DONE)
The management webapp: charts, tables, trends, outlook, CSV export — and a solid,
runnable core that works on any computer with practice data.
**You have this today.**

> **Production hardening applied:** server binds localhost by default, optional
> access token, Chart.js vendored locally (no CDN), system fonts, dynamic
> year/version/outlook detection from the database, report generation API
> endpoints, spreadsheet formula-injection protection in all exports, and
> post-load data validation on every database load.

### Stage 1 — Take in real data (the extraction engine) ⭐ the keystone — *foundation built*

> **Status:** the engine foundation exists in `extractor/` — it captures Excel
> and Word into faithful raw JSON today (tested), with COM-first Excel for
> Windows and PDF/Outlook extractors written and ready to switch on. Captured
> **spreadsheet** raw JSON can now reach the dashboard database via
> `map_raw_to_db.py` and a reviewed per-client mapping (`mapping.example.json`).
> Still to do: the scanned-PDF OCR path, live-Outlook COM, and mappings for
> non-spreadsheet sources. See `extractor/README.md`.

A drop-folder where you put a client's **Excel, PDF, and Word** files. The system
reads them, pulls out the real numbers, and loads them into the fast database.
Every original is also saved **exactly as-is in JSON** so nothing is ever lost.
- **Why it matters:** this is what lets you actually *go to a client* and turn
  their mess into the dashboard. Everything downstream becomes real.
- **Honesty about difficulty:** Excel is the easiest. PDFs and Word vary wildly —
  clean digital PDFs are doable; **scanned/photographed documents** need
  text-recognition (OCR) and AI, and usually a quick **"check what was
  extracted"** step before trusting it. We start with the easy wins and grow.

### Stage 2 — The reports engine — *first version built*
Define report templates once, then generate them from the database on demand.
Each report is also saved as JSON (your "target" format) and shown in the webapp
or exported to Excel/PDF.

> **Status:** `reports/` generates eight reports from the database — six core
> P&L reports plus two **forecast/outlook** reports (full-year outlook vs prior
> year, and monthly progression) — as self-describing JSON, CSV,
> **management-ready Excel (.xlsx)** and **PDF**, and bundles them all into a
> single **board pack** (`--pack`). The six core SQL reports are also available
> as live API endpoints (`/api/reports`, `/api/reports/generate`). See
> `reports/README.md`. Next: client-specific templates, report download UI in
> the dashboard.

### Stage 3 — Scenarios & forecasting — *first version built*
"What-if" modelling and forward forecasts — change an assumption and watch the
outlook update. (The dashboard's outlook tab is an early piece of this.)

> **Status:** `reports/scenario.py` applies a reviewable JSON of assumption
> "levers" (e.g. "Asia Pacific net sales -10%", "opex +3%") to the baseline
> outlook and produces a baseline-vs-scenario P&L (JSON/CSV/Excel/PDF) — see
> `scenario.example.json`. Zero-adjustment scenarios reproduce the baseline
> exactly. Next: multi-scenario comparison, scenarios in the live dashboard,
> volume/price decomposition.

### Stage 4 — The "second brain" (Obsidian-style wiki) — *first version built*
A linked knowledge base of the company: how things work, definitions, decisions,
meeting notes — connected to the live data so knowledge and numbers live together.

> **Status:** `knowledge/` holds Obsidian-compatible Markdown notes
> (`[[wiki-links]]`, `#tags`, frontmatter) and `brain/` parses them into a graph
> — backlinks, orphans, broken-link validation, a tag index, an auto-generated
> index, and **region notes generated from the database** so knowledge links to
> live numbers. See `brain/README.md`. Next: more curated content, full-text
> search, an HTML/graph viewer, links from notes into specific reports.

### Stage 5 — The AI agent ("Hermes")
An assistant that learns the company's workflows, does the repetitive work,
automates steps, and suggests better ways of working.
- **Why it's last:** an agent needs the data, reports, and knowledge base
  (Stages 1–4) to already exist before it has anything to act on.

### Stage 6 — Arabic-first robustness (cross-cutting) — *first version building*
This product runs **mainly on Arabic data**, so Arabic is a first-class concern
across the whole pipeline, not a translation layer bolted on at the end. This
stage runs alongside the others (it touches extraction, mapping, reports and the
dashboard) rather than strictly after them.

**Locked decisions:** Gregorian calendar only (no Hijri); the dashboard becomes a
full right-to-left (RTL) Arabic UI; extraction must cover `.xlsx/.xlsm/.xlsb/.xls`
and CSV/TSV; Arabic spelling variants of a name are **grouped together for totals
but shown with their original spelling**; dashboard digits are user-toggleable
(Western ↔ Arabic-Indic); the Arabic font (**Cairo**, OFL) is vendored locally
to respect the no-CDN rule.

> **Sub-stages:**
> - **6.1 Normalization core — *done*.** `extractor/arabic.py`: a shared,
>   dependency-light module with the key *match-key vs display-value* split —
>   `clean_display` (what we store/show, letters never altered) and `match_key`
>   (folds alef/yaa/taa-marbuta/hamza + diacritics + digits, for matching and
>   grouping only), plus `parse_number` (Arabic digits, ٬/٫ separators, currency,
>   accounting negatives) and Gregorian `month_to_number`. Tested + in CI.
> - **6.2 Arabic-aware mapper.** Match headers/sheets via `match_key`; parse
>   numbers/periods via the core; store a normalized group key beside the
>   original value so reports total correctly without renaming anything. Golden
>   Arabic fixtures.
> - **6.3 Format & fidelity.** `.xlsb` (pyxlsb), `.xls` (xlrd), CSV/TSV with
>   encoding auto-detection (Windows-1256 vs UTF-8±BOM); merged-cell and
>   multi-row headers, formula-without-cache detection, error cells, numbers
>   stored as text.
> - **6.4 Export correctness.** CSV written with a UTF-8 BOM (so Excel on Arabic
>   Windows reads it); PDF board packs reshaped + bidi-ordered with the embedded
>   Cairo font and right-aligned RTL tables; XLSX sheets flagged right-to-left.
> - **6.5 Full RTL dashboard.** `dir="rtl"`/`lang="ar"`, vendored Cairo webfont,
>   CSS logical properties so the layout mirrors cleanly, bidi-isolated numbers,
>   RTL-configured Chart.js, a small en/ar string map and a language + digit
>   toggle. An Arabic synthetic dataset in `seed_db.py` so it's testable in CI.

---

## Big decisions to keep in mind (not all today)

- **Where it runs & privacy.** Client financial data is sensitive. The server
  defaults to `127.0.0.1` (local only) with an optional `ACCESS_TOKEN` for
  shared deployments. All assets are self-contained (no external CDN).
- **One client or many.** A tool for one client at a time is much simpler than a
  product that serves many companies at once. We can start with one and grow.
- **Human-in-the-loop.** Especially for messy PDFs, a person confirming the
  extracted numbers keeps trust high. The AI does 90%; a quick review catches the
  rest.

---

## Recommended order

1. **Stage 1 first** — it unlocks real client work and feeds everything else.
2. Then **Stage 2 (reports)** and **Stage 3 (scenarios)** to deepen the value.
3. Then **Stage 4 (knowledge base)**.
4. Then **Stage 5 (the AI agent)**, once there's a real system for it to run.

Each stage ships something you can use and show — no waiting months for a "big
reveal."
