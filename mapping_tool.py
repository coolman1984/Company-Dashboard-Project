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


def scan_raw_files(raw_dir: str) -> list[dict]:
    """Scan raw/*.raw.json files and extract sheet names + headers.
    
    Returns list of:
        {"file": "filename.raw.json", "sheet": "Sheet Name",
         "headers": ["Col1", "Col2", ...], "sample_rows": [[...], ...]}
    """
    results = []
    if not os.path.isdir(raw_dir):
        return results
    
    for fname in sorted(os.listdir(raw_dir)):
        if not fname.endswith(".raw.json"):
            continue
        path = os.path.join(raw_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        
        if envelope.get("document_type") != "spreadsheet":
            continue
        
        content = envelope.get("content", {})
        for sheet in content.get("sheets", []):
            cells = sheet.get("cells", [])
            if not cells:
                continue
            headers = [str(c) if c is not None else "" for c in cells[0]]
            sample_rows = cells[1:6]  # first 5 data rows as samples
            results.append({
                "file": fname,
                "sheet": sheet.get("name", "unnamed"),
                "headers": headers,
                "n_rows": sheet.get("n_rows", 0),
                "sample_rows": sample_rows,
            })
    
    return results


# Common header → DB column mappings (bilingual)
KNOWN_PATTERNS = {
    "year": "year", "السنة": "year", "سنة": "year",
    "version": "version", "النسخة": "version",
    "period": "period", "الفترة": "period", "فترة": "period",
    "region": "region_desc", "المنطقة": "region_desc", "منطقة": "region_desc",
    "country": "country_name", "الدولة": "country_name", "دولة": "country_name",
    "customer": "customer_name", "العميل": "customer_name", "عميل": "customer_name",
    "net sales": "net_sales", "صافي المبيعات": "net_sales",
    "gross margin": "gross_margin", "إجمالي الربح": "gross_margin",
    "cogs": "cost_of_goods_sold", "تكلفة المبيعات": "cost_of_goods_sold",
    "operating profit": "operating_profit", "الربح التشغيلي": "operating_profit",
    "net income": "net_income", "صافي الدخل": "net_income",
    "product group": "m_group_desc", "مجموعة المنتجات": "m_group_desc",
}


def _normalize(text: str) -> str:
    """Normalize text for matching using Arabic match_key + lowercase."""
    if not text:
        return ""
    # Use Arabic normalization (folds alef/yaa/hamza/diacritics)
    text = arabic.match_key(text)
    # Also lowercase and strip
    return text.lower().strip()


def _score_match(source_header: str, db_column: str) -> tuple[float, str]:
    """Score how well a source header matches a DB column.
    
    Returns (score, method) where:
      - 1.0 = exact match
      - 0.9 = known pattern match
      - 0.7 = normalized match (Arabic)
      - 0.5 = fuzzy match (substring)
      - 0.0 = no match
    """
    src = source_header.strip()
    src_lower = src.lower()
    db_col = db_column.lower()
    
    # Exact match
    if src_lower == db_col:
        return 1.0, "exact"
    
    # Known pattern
    if src_lower in KNOWN_PATTERNS:
        if KNOWN_PATTERNS[src_lower] == db_column:
            return 0.9, "known_pattern"
    
    # Normalized match (Arabic-aware)
    src_norm = _normalize(src)
    db_norm = _normalize(db_column)
    if src_norm and db_norm and src_norm == db_norm:
        return 0.7, "normalized"
    
    # Substring match (db column name contains source or vice versa)
    if db_col.replace("_", " ") in src_lower or src_lower in db_col.replace("_", " "):
        return 0.5, "substring"
    
    return 0.0, "none"


def suggest_mappings(sheets: list[dict], schema_cols: dict) -> list[dict]:
    """For each sheet, suggest column mappings.
    
    Returns list of:
        {"file": "...", "sheet": "...", "suggestions": [
            {"source": "Year", "target": "year", "score": 1.0, "method": "exact"},
            ...
        ]}
    """
    db_columns = list(schema_cols.keys())
    results = []
    
    for sheet in sheets:
        suggestions = []
        for header in sheet["headers"]:
            if not header or not header.strip():
                continue
            
            best_score = 0.0
            best_match = None
            best_method = "none"
            
            for db_col in db_columns:
                score, method = _score_match(header, db_col)
                if score > best_score:
                    best_score = score
                    best_match = db_col
                    best_method = method
            
            suggestions.append({
                "source": header,
                "target": best_match if best_score > 0.3 else None,
                "score": best_score,
                "method": best_method,
                "confidence": "high" if best_score >= 0.7 else
                              "medium" if best_score >= 0.5 else "low",
            })
        
        results.append({
            "file": sheet["file"],
            "sheet": sheet["sheet"],
            "n_rows": sheet["n_rows"],
            "suggestions": suggestions,
            "sample_rows": sheet.get("sample_rows", []),
        })
    
    return results


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
