# Arabic Stage 6 Handoff Plan

This is the execution plan for the next agent continuing the Arabic-first work.
Read `AGENTS.md` and `ROADMAP.md` first, then use this file as the task plan.

## Current State

- Arabic-first RTL dashboard is live on `main`.
- `index.html` defaults to `lang="ar" dir="rtl"`.
- `cairo.ttf` is vendored and served locally.
- `i18n.js` handles language and digit toggles, defaulting to Arabic with Western digits.
- `app.js` routes Chart.js canvas labels/tooltips/axis titles through `tr()` for Arabic mode.
- `i18n.js` has an exact-phrase Arabic map plus a MutationObserver for dynamic DOM text.
- Arabic extraction basics are implemented and tested:
  - `extractor/arabic.py`
  - `extractor/csv_text.py`
  - `extractor/excel_xls.py`
  - `extractor/excel_xlsb.py`
- CSV Arabic encoding and Excel RTL report sheet support exist.
- Arabic PDF rendering is not complete.

## Non-Negotiable Rules

- Do not change financial definitions or invent new metrics.
- Keep Gregorian dates only.
- Keep original Arabic spellings exactly as typed in source data; do not merge variants in totals unless the owner explicitly reverses the prior decision.
- Preserve English mode layout and text behavior.
- Do not add external CDN dependencies. All fonts/assets must be local.
- Do not commit client data from `intake/`, `raw/`, generated reports, or generated knowledge data.
- Run the verification commands at the end before pushing.

## Recommended Work Order

### 1. Browser Visual QA For Arabic RTL

Goal: catch spacing, overflow, clipping, bad alignment, chart readability, and regressions in English mode.

Manual checks:
- Start the app: `python3 seed_db.py --force && npm start`.
- Open `http://localhost:3001`.
- Check Arabic default mode on desktop width around `1440x900`.
- Check Arabic default mode on mobile width around `390x844`.
- Click every tab: Overview, Regional, Products, Variance, Scenario, Trends, Portfolio.
- Toggle English and confirm the original LTR layout/text still works.
- Toggle Arabic-Indic digits and confirm numbers change without breaking chart/table layout.
- Export CSV from a few tables and confirm Arabic filenames/content still open correctly.

What to look for:
- Sidebar labels cut off or wrapping badly.
- Topbar filters too cramped in RTL.
- Chart legends clipped or overlapping.
- Table sticky first column behaving incorrectly in RTL.
- Chart tooltips still showing English labels.
- Text that remains English because it is not in `AR_TEXT` and not routed through `tr()`.
- Mixed Arabic/English punctuation that reads awkwardly.

Likely files:
- `index.html`
- `app.js`
- `i18n.js`

Acceptance criteria:
- Arabic dashboard is usable on desktop and mobile.
- English mode remains visually unchanged or very close to the previous layout.
- Any remaining English strings are either fixed or listed as intentional technical terms.

### 2. Finish Any Remaining UI Translation Gaps

Goal: complete the remaining English labels after real browser inspection.

Approach:
- If the English text is static HTML, either add a `data-i18n` key or add the exact phrase to `AR_TEXT`.
- If the English text is inserted into DOM by `app.js`, prefer adding the exact phrase to `AR_TEXT`; the MutationObserver should handle it.
- If the English text appears inside Chart.js canvas labels/tooltips/axis titles, route it through `tr()` in `app.js`.
- If the string is dynamic, add a regex rule in `translateText()` only when exact keys are not practical.

Examples:
- Exact phrase: add to `AR_TEXT`.
- Dynamic phrase like `FY2026 outlook`: add a regex rule to `translateText()`.
- Chart dataset label: set `label: tr('Revenue')`.
- Chart tooltip: call `tr()` inside the callback.

Avoid:
- Translating customer names, product names, region names, or source-data values.
- Translating API keys, metric keys, class names, dataset object keys, or table IDs.

Acceptance criteria:
- No visible English UI labels remain in Arabic mode except accepted technical abbreviations such as `CSV`, `SQLite`, `HHI`, `T06`, `T07`, `P01`.
- English mode still uses original English text.

### 3. Arabic Sample/Seed Display Data

Goal: make the sample dashboard feel Arabic-first, not just Arabic UI over English sample dimensions.

Important decision:
- This should be sample/demo data only. Do not alter real client-data behavior.

Recommended approach:
- Add optional Arabic seed mode to `seed_db.py`, for example `python3 seed_db.py --force --locale ar`.
- Keep default seed behavior unchanged unless the owner wants Arabic as the default demo data too.
- Use Arabic names for regions/countries/customers/product groups in the Arabic seed path.
- Keep the schema unchanged.
- Keep financial calculations identical to current synthetic generation.

Likely files:
- `seed_db.py`
- `test_db.js` or smoke tests if assumptions depend on English dimensions
- `README.md`
- `GETTING-STARTED.md`
- `AGENTS.md`

Suggested Arabic sample dimensions:
- Regions: الشرق الأوسط، أوروبا، آسيا والمحيط الهادئ، الأمريكتان، أفريقيا
- Countries: مصر، السعودية، الإمارات، ألمانيا، الولايات المتحدة، جنوب أفريقيا
- Customers: عميل ألف، عميل باء, شركة النور, شركة المستقبل
- Product groups: الأجهزة، الخدمات، البرمجيات، قطع الغيار، حلول المؤسسات

Acceptance criteria:
- `python3 seed_db.py --force --locale ar` creates a working DB.
- Arabic source values display correctly in tables/charts.
- Existing `python3 seed_db.py --force` remains compatible with current tests.
- Tests pass with the default seed.
- If adding Arabic seed tests, include at least one test that Arabic dimension names survive API round-trip.

### 4. Arabic PDF Rendering (Stage 6.4b)

Goal: generated PDF reports render Arabic correctly: connected letters, correct RTL order, and an Arabic-capable font.

Font decision needed first:
- Recommended: **Noto Naskh Arabic** for reports because it is conservative and readable in financial documents.
- Alternative: **Amiri** if the owner prefers a traditional book/report style.
- Existing `cairo.ttf` can be used for a quick proof, but it may not be ideal for dense PDF tables.

Technical reality:
- ReportLab does not fully shape Arabic by itself.
- Arabic PDF usually needs both:
  - an Arabic-capable TTF font registered with ReportLab
  - shaping/bidi preprocessing, commonly `arabic-reshaper` + `python-bidi`

Recommended implementation:
- Vendor the chosen `.ttf` font locally, for example `fonts/NotoNaskhArabic-Regular.ttf`.
- Add the font license file or source note.
- Add optional dependencies to `reports/requirements.txt`:
  - `arabic-reshaper`
  - `python-bidi`
- Add helper functions in `reports/render.py`:
  - detect Arabic text
  - reshape/bidi Arabic text for PDF only
  - register Arabic font once
  - apply RTL alignment to Arabic table cells where practical
- Keep Excel behavior separate. Excel already supports RTL sheet view.
- If dependencies are missing, PDF rendering should fail with a clear actionable error, not a traceback.

Likely files:
- `reports/render.py`
- `reports/requirements.txt`
- `reports/test_render.py`
- `.github/workflows/ci.yml`
- `README.md`
- `reports/README.md`
- New font file and license/source note

Testing strategy:
- Add a small Arabic report envelope fixture in `reports/test_render.py`.
- Generate a PDF with Arabic title and at least one Arabic table cell.
- Test should verify the PDF file is created and non-empty.
- If text extraction is reliable, optionally assert recognizable shaped output; do not make CI fragile if extraction varies.

Acceptance criteria:
- `python3 -m reports.test_render` passes.
- A generated Arabic PDF visually shows connected Arabic letters in the correct order.
- English PDFs remain unchanged.
- CI installs the new PDF Arabic dependencies and passes.

### 5. Documentation Updates

Goal: keep the next agent/user from guessing what changed.

Update as work lands:
- `README.md`
- `GETTING-STARTED.md`
- `reports/README.md`
- `ROADMAP.md`
- `AGENTS.md` task board and journal

Docs must state:
- Whether Arabic sample data exists and how to generate it.
- Which PDF Arabic font was chosen and why.
- Whether Arabic PDF dependencies are required or optional.
- Any known remaining visual issues.

### 6. Final Verification Before Push

Run these from repo root:

```bash
npm test
python3 -m extractor.test_arabic
python3 -m extractor.test_extractor
python3 test_map_raw_to_db.py
python3 -m reports.test_reports
python3 -m reports.test_render
python3 -m reports.test_scenario
python3 -m brain.test_brain
python3 -m brain.cli --check
```

If system Python blocks packages, use a venv:

```bash
python3 -m venv /tmp/opencode/company-dashboard-venv
/tmp/opencode/company-dashboard-venv/bin/pip install -r extractor/requirements.txt -r reports/requirements.txt
/tmp/opencode/company-dashboard-venv/bin/python -m extractor.test_arabic
```

Also run:

```bash
git diff --check
git status --short --branch
```

## Suggested Commit Split

Use separate commits if the work gets large:

1. `Polish Arabic RTL dashboard visual details`
2. `Add Arabic sample seed data option`
3. `Add Arabic PDF rendering support`
4. `Update Arabic Stage 6 documentation`

## Remaining Backlog After This Plan

- Arabic PDF 4b.
- Arabic seed/sample display data.
- RTL browser visual polish.
- Optional: replace exact-phrase translation map with a more structured i18n key system if the UI grows.
