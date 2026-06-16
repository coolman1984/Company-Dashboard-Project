# Sample Data — complete lineage demo

This folder contains a small synthetic raw capture and mapping that exercise the
full import path without private client data:

```bash
python3 map_raw_to_db.py \
  --mapping sample_data/mapping.complete.json \
  --raw sample_data \
  --db /tmp/company-dashboard-sample.db

python3 -m reports.cli --db /tmp/company-dashboard-sample.db --report import_validation
```

The raw file is shaped like extractor spreadsheet output and includes a realistic
source block. Loading it creates:

- `pl_detail` ledger rows
- `import_run` metadata
- `source_file` metadata
- `row_lineage` entries that point each ledger row back to source file, sheet and row

All data is synthetic and safe to commit.
