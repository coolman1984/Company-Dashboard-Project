#!/usr/bin/env python3
"""
mapping_tool.py — auto-suggest column mappings from raw JSON captures.

Scans raw/*.raw.json files, extracts sheet names and headers, suggests
DB column mappings using exact match, Arabic normalization, and fuzzy
matching, and generates an HTML review report.

Usage:
    python3 mapping_tool.py --raw raw/ --output mapping_review.json
    python3 mapping_tool.py --raw raw/ --report mapping_review.html
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from extractor import arabic
import db_schema


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Auto-suggest column mappings from raw JSON captures.")
    parser.add_argument("--raw", default="raw",
                        help="Folder of raw/*.raw.json captures.")
    parser.add_argument("--schema", default="schema.sql",
                        help="Path to schema.sql.")
    parser.add_argument("--output", default=None,
                        help="Output mapping JSON path (default: stdout).")
    parser.add_argument("--report", default=None,
                        help="Output HTML review report path.")
    args = parser.parse_args(argv)
    
    # 1. Scan raw files
    sheets = scan_raw_files(args.raw)
    if not sheets:
        print(f"No spreadsheet raw files found in {args.raw}", file=sys.stderr)
        return 1
    
    # 2. Load schema columns
    schema_cols = db_schema.column_types(args.schema)
    
    # 3. Suggest mappings
    suggestions = suggest_mappings(sheets, schema_cols)
    
    # 4. Output
    if args.report:
        write_html_report(args.report, sheets, suggestions, schema_cols)
        print(f"Review report written to {args.report}")
    
    mapping = build_mapping(suggestions)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        print(f"Mapping written to {args.output}")
    else:
        print(json.dumps(mapping, indent=2, ensure_ascii=False))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
