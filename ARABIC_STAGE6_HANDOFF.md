# Arabic Stage 6 Current State

This file is the handoff note for agents continuing the Arabic-first work. Read `AGENTS.md` and `ROADMAP.md` first.

## Current state on `main`

- Arabic-first RTL dashboard is live on `main`.
- `index.html` defaults to `lang="ar" dir="rtl"`.
- `cairo.ttf` is vendored and served locally for the UI.
- `i18n.js` handles language and digit toggles, defaulting to Arabic with Western digits.
- `app.js` routes key Chart.js labels/tooltips/axis titles through `tr()` for Arabic mode.
- Dynamic UI translation covers page headings, status/freshness messages, KPI labels, table headers, common signals, and management-action text.
- Arabic extraction basics are implemented and tested:
  - `extractor/arabic.py`
  - `extractor/csv_text.py`
  - `extractor/excel_xls.py`
  - `extractor/excel_xlsb.py`
- `extractor/requirements.txt` includes the cross-platform spreadsheet dependencies: `openpyxl`, `pyxlsb`, and `xlrd`.
- CSV Arabic encoding and Excel RTL report sheet support exist.
- Arabic PDF rendering uses HTML/CSS → WeasyPrint: `reports/render.py` builds an
  RTL HTML string and renders it to PDF for correct connected Arabic glyphs.
  The vendored `fonts/NotoNaskhArabic.ttf` is used by WeasyPrint automatically.
- `reports/test_render.py` creates English and Arabic PDF artifacts and asserts
  the Arabic rendering path when dependencies are installed.
- Arabic board pack (`reports.cli --pack`) is available and includes a final
  **source-confidence / import-validation** page.
- Import validation report (`reports/validation.py`) summarises row counts,
  null checks, duplicate-grain checks, and dimension coverage.
- Arabic pilot demo script exists at `docs/client-demo-script.md`.
- Arabic sample data is available with:

```bash
python3 seed_db.py --force --locale ar
```

## Non-negotiable rules

- Do not change financial definitions or invent new metrics.
- Keep Gregorian dates only.
- Keep original Arabic spellings exactly as typed in source data; do not merge variants in totals unless the owner explicitly reverses the prior decision.
- Preserve English mode layout and text behavior.
- Do not add external CDN dependencies. All fonts/assets must be local.
- Do not commit client data from `intake/`, `raw/`, generated reports, or generated knowledge data.
- Run the verification commands before pushing.

## Browser visual QA already performed in this pass

Checked manually with Playwright against a locally running server and Arabic seed data:

- Arabic desktop viewport around `1280x720`.
- Arabic mobile viewport around `390x844`.
- English toggle on desktop.
- Live `/api/status` and `/api/summary` after startup.

Issues found and addressed:

- Page heading stayed English on initial Arabic load because the initial active tab did not refresh the heading through `I18N.t()`; fixed in `app.js`.
- Several dynamic status/KPI/table phrases remained English; expanded `i18n.js` exact and regex translations.
- Documentation still described Arabic PDF as pending; updated the docs to reflect the current implementation.

## Remaining work

1. English desktop and tablet/mobile browser QA.
2. Client-specific Arabic wording polish once real client sample files exist.
3. Better automated browser assertions for Arabic mode if a lightweight browser test path is added.
4. Source drill-back from dashboard numbers to source rows/files (Phase 2).
5. Future extraction work: scanned-PDF OCR, merged/multi-row spreadsheet headers, formula-without-cache detection, and Windows COM validation.

## Final verification command set

Run from repo root:

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
git diff --check
git status --short --branch
```

If system Python blocks packages, use a venv:

```bash
python3 -m venv /tmp/company-dashboard-venv
/tmp/company-dashboard-venv/bin/pip install -r extractor/requirements.txt -r reports/requirements.txt
/tmp/company-dashboard-venv/bin/python -m reports.test_render
```
