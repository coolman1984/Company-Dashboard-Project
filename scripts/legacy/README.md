# scripts/legacy — archived one-off scripts

These were early/manual scripts from before the project settled on its current
architecture (SQLite-first, the `extractor/` engine, and `schema.sql` as the one
source of truth via `db_schema.py`). They are **kept for history and reference
only** — they are not part of the pipeline, are not run in CI, and may reference
paths or assumptions that no longer hold. See [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
for the current design.

| Script | What it did | Superseded by |
|--------|-------------|---------------|
| `precompute_data.py` | Pre-computed every query to JSON for a static server | Live SQLite queries in `server.js` |
| `create_indexes_views.py` | Built indexes/views in Python | `schema.sql` applied via `db_schema.py` |
| `create_dynamic_indexes.js` | Ad-hoc index creation in Node | `schema.sql` (indexes defined there) |
| `explore_sheet1.py` | One-off COM exploration of the .xlsb | `extractor/` engine + `extractor/com_utils.py` |
| `extract_pl_data.py` | One-off COM dump of a pivot sheet to JSON | `extractor/` engine + `ingest_sheet1.py` |
| `analysis_cfo.py` | Offline CFO analysis experiments | `reports/` engine |
| `check_db.py` | Quick row-count/size check | `reports/` validation + `test_db_schema.py` |
| `verify_db.py` | Verify views/indexes exist | `test_db_schema.py` |
| `test_db.js` | Ad-hoc DB poke from Node | `smoke_test.js` + `test_db_schema.py` |

If you need one of these again, lift the useful part into the proper layer
(`extractor/`, `reports/`, or a test) rather than reviving the script at the root.
