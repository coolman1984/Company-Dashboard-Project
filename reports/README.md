# Reports Engine (Stage 2)

**Generate saved report files (JSON, CSV, Excel, and PDF) from the dashboard
database** — the "target reports as JSON" stage of [ROADMAP.md](../ROADMAP.md),
extended into management-ready artifacts.

The dashboard (`server.js`) serves analytics *live* in the browser. This engine
produces **durable, shareable report artifacts** you can attach to a board pack,
email, or archive — each a self-describing file that stands on its own.

## How to run it

```bash
python3 -m reports.cli --list                  # show available reports
python3 -m reports.cli                          # generate all as JSON -> output/reports/
python3 -m reports.cli --report yearly_pl       # just one
python3 -m reports.cli --format json csv xlsx pdf   # all four formats
python3 -m reports.test_reports                 # run the tests

# Board pack: bundle ALL reports into ONE file you hand to management.
python3 -m reports.cli --pack                    # board-pack.xlsx + board-pack.pdf
python3 -m reports.cli --pack --title "FY2026 Board Pack"
```

The **board pack** is a single combined artifact: one Excel workbook with a
Contents sheet plus a tab per report, and/or one PDF with a cover page and a
section per report.

The source database must exist first — either the synthetic dev data
(`python3 seed_db.py`) or real client data loaded via `map_raw_to_db.py`.

### Live API access (from the dashboard)

The six core SQL-based reports are also available as live API endpoints:

```bash
curl http://localhost:3001/api/reports                    # list reports
curl http://localhost:3001/api/reports/generate?name=yearly_pl  # JSON report
```

No Python needed — the server runs the report SQL directly against the live database.

### Export safety

All CSV and Excel exports are protected against spreadsheet formula injection:
string cells beginning with `=`, `+`, `-`, `@`, tab, or carriage return are
automatically prefixed with `'` before writing. This is handled by `safe_str()`
in `reports/__init__.py` and applied in both the CSV writer and Excel renderer.

### Output formats

| Format | Needs | Use |
|--------|-------|-----|
| `json` | nothing (stdlib) | the durable "target report" envelope; feeds other tools |
| `csv`  | nothing (stdlib) | open in any spreadsheet |
| `xlsx` | `openpyxl` | **management-ready Excel** — titled, formatted, real numbers, Arabic sheets marked right-to-left |
| `pdf`  | `reportlab`; Arabic text also uses `arabic-reshaper` + `python-bidi` + vendored Noto Naskh Arabic | **management-ready PDF** — landscape, formatted table, Arabic text shaped/bidi-corrected when dependencies are installed |

Install the office-format libraries with `pip install -r reports/requirements.txt`.
Excel/PDF rendering is optional and degrades gracefully — if a library is
missing, the CLI says so instead of crashing. Arabic PDF rendering uses the
local font at `fonts/NotoNaskhArabic.ttf`; keep this font and its license/source
note with the repo so reports stay offline and CDN-free.

## What a report looks like (the "target" JSON envelope)

```jsonc
{
  "report": "yearly_pl",
  "title": "Yearly P&L Summary",
  "description": "...",
  "generated_at": "2026-06-14T09:32:50Z",
  "source": { "database": "pl_detail.db", "rows_in_ledger": 7560 },
  "columns": ["year", "net_sales", "gross_margin", "..."],
  "row_count": 5,
  "rows": [ { "year": 2022, "net_sales": 100847487.78, "...": "..." } ]
}
```

Metadata wraps the content, so each report is auditable on its own (what it is,
when it was made, from which database).

## Available reports

| Name | Description |
|------|-------------|
| `yearly_pl` | Group-wide P&L by fiscal year |
| `regional_pl` | P&L by region and year |
| `product_group_pl` | P&L by product group and year |
| `country_pl` | P&L by country and year |
| `customer_pl` | P&L by customer and year |
| `yoy_variance` | Year-over-year change in key P&L lines |
| `outlook_pl` | **Forecast** full-year P&L (Actual P01-P05 + T06 P06 + T07 P07-P12) vs prior-year actual, with variance |
| `outlook_monthly` | Monthly net sales / gross margin, flagged actual vs outlook |

Most read the Actual-only views in `schema.sql`, so figures tie out with the
dashboard. The `outlook_*` reports are *computed* (forecast) reports defined in
`reports/outlook.py` — they stitch the version/period coverage into a
forward-looking full-year view, the same way the dashboard's executive outlook
does.

## What-if scenarios

`reports/scenario.py` models a decision before you take it: apply a small,
reviewable JSON of assumption "levers" to the baseline outlook and get a
baseline-vs-scenario P&L (JSON/CSV/Excel/PDF). See `scenario.example.json`.

```bash
python3 -m reports.scenario --scenario scenario.example.json
python3 -m reports.scenario --scenario scenario.example.json --format json xlsx pdf
```

Levers are per-dimension percentage changes to net sales, COGS, or operating
expense (e.g. `{"metric": "net_sales", "change_pct": -10, "where": {"region_desc": "Asia Pacific"}}`).
COGS optionally scales with revenue volume. Lines below operating profit move by
identity on the delta, so a scenario with no adjustments reproduces the baseline
exactly.

## Adding a report

Append a `Report` to `reports/definitions.py`. A report is either:
- **SQL-backed:** pass `sql="SELECT ..."` (usually over a `schema.sql` view), or
- **computed:** pass `builder=fn`, where `fn(conn) -> (columns, rows[, extra])`
  (see `reports/outlook.py`). `extra` adds envelope metadata such as `basis`.

No other code changes needed. Generated files go to `output/reports/` and are
git-ignored (they can derive from real client data).
