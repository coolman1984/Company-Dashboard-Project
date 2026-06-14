# Reports Engine (Stage 2)

**Generate saved report files (JSON + CSV) from the dashboard database** — the
"target reports as JSON" stage of [ROADMAP.md](../ROADMAP.md).

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
```

The source database must exist first — either the synthetic dev data
(`python3 seed_db.py`) or real client data loaded via `map_raw_to_db.py`.

### Output formats

| Format | Needs | Use |
|--------|-------|-----|
| `json` | nothing (stdlib) | the durable "target report" envelope; feeds other tools |
| `csv`  | nothing (stdlib) | open in any spreadsheet |
| `xlsx` | `openpyxl` | **management-ready Excel** — titled, formatted, real numbers |
| `pdf`  | `reportlab` | **management-ready PDF** — landscape, formatted table |

Install the office-format libraries with `pip install -r reports/requirements.txt`.
Excel/PDF rendering is optional and degrades gracefully — if a library is
missing, the CLI says so instead of crashing.

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

All read the Actual-only views in `schema.sql`, so figures tie out with the
dashboard by construction.

## Adding a report

Append a `Report` to `reports/definitions.py` (name, title, description, SQL).
No other code changes needed. Generated files go to `output/reports/` and are
git-ignored (they can derive from real client data).
