# Mapping Review Tool — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a CLI tool that reads a raw JSON capture, auto-suggests column mappings to the database schema, and produces a reviewable HTML report + a validated mapping.json file.

**Architecture:** Python CLI (`mapping_tool.py`) that: (1) scans raw JSON files to extract sheet names and headers, (2) suggests DB column mappings using exact match, Arabic normalization, and fuzzy matching, (3) generates an HTML review report the operator opens in a browser, (4) exports a validated mapping.json. Zero new dependencies — uses stdlib + the project's own `extractor.arabic` module.

**Tech Stack:** Python 3 stdlib, `extractor.arabic` (Arabic normalization), `jinja2`-style HTML templating (inline, no dependency).

---

## Task 1: Create `mapping_tool.py` skeleton with CLI args

**Objective:** Set up the CLI entry point with `--raw`, `--schema`, `--output` arguments.

**Files:**
- Create: `mapping_tool.py`

**Step 1: Create the skeleton**

```python
#!/usr/bin/env python3
"""
mapping_tool.py — auto-suggest column mappings from raw JSON captures.

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
```

**Step 2: Verify it parses**

Run: `python3 -c "import mapping_tool"`
Expected: No error

**Step 3: Commit**

```bash
git add mapping_tool.py
git commit -m "feat: mapping_tool skeleton with CLI args"
```

---

## Task 2: Implement `scan_raw_files()` — extract sheets and headers

**Objective:** Walk the raw folder, find spreadsheet-type captures, extract sheet names and header rows.

**Files:**
- Modify: `mapping_tool.py`

**Step 1: Add the function**

```python
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
```

**Step 2: Test with synthetic data**

Run:
```python
python3 -c "
import json, os, tempfile
from mapping_tool import scan_raw_files

# Create a fake raw file
tmp = tempfile.mkdtemp()
envelope = {
    'document_type': 'spreadsheet',
    'content': {'sheets': [{'name': 'P&L', 'n_rows': 10,
        'cells': [['Year', 'Region', 'Net Sales'], [2025, 'Africa', 1000]]}]}
}
with open(os.path.join(tmp, 'test.raw.json'), 'w') as f:
    json.dump(envelope, f)

results = scan_raw_files(tmp)
print(results)
assert len(results) == 1
assert results[0]['headers'] == ['Year', 'Region', 'Net Sales']
print('OK')
"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add mapping_tool.py
git commit -m "feat: scan_raw_files extracts sheets and headers"
```

---

## Task 3: Implement `suggest_mappings()` — match headers to DB columns

**Objective:** For each source header, suggest the best DB column match using exact match, Arabic normalization, and fuzzy matching.

**Files:**
- Modify: `mapping_tool.py`

**Step 1: Build the suggestion engine**

```python
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
```

**Step 2: Test with known headers**

Run:
```python
python3 -c "
from mapping_tool import suggest_mappings
sheets = [{'file': 'test.raw.json', 'sheet': 'P&L', 'n_rows': 10,
    'headers': ['Year', 'المنطقة', 'Net Sales', 'Unknown'], 'sample_rows': []}]
schema_cols = {'year': 'INTEGER', 'region_desc': 'TEXT', 'net_sales': 'REAL'}
results = suggest_mappings(sheets, schema_cols)
s = results[0]['suggestions']
print(s)
assert s[0]['target'] == 'year' and s[0]['confidence'] == 'high'
assert s[1]['target'] == 'region_desc'  # Arabic match
assert s[2]['target'] == 'net_sales'
assert s[3]['target'] is None  # no match
print('OK')
"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add mapping_tool.py
git commit -m "feat: suggest_mappings with exact/Arabic/fuzzy matching"
```

---

## Task 4: Implement `build_mapping()` — convert suggestions to mapping JSON

**Objective:** Convert the reviewed suggestions into a valid mapping.json structure.

**Files:**
- Modify: `mapping_tool.py`

**Step 1: Add the function**

```python
def build_mapping(suggestions: list[dict], constants: dict = None) -> dict:
    """Convert suggestions into a mapping.json structure.
    
    The operator can edit the suggestions before calling this.
    """
    if not suggestions:
        return {}
    
    # Use the first sheet by default
    sheet = suggestions[0]
    
    columns = {}
    for s in sheet["suggestions"]:
        if s["target"] and s["confidence"] in ("high", "medium"):
            columns[s["source"]] = s["target"]
    
    mapping = {
        "source_glob": f"*{sheet['file'].replace('.raw.json', '')}*",
        "sheet": sheet["sheet"],
        "header_row": 0,
        "skip_blank_rows": True,
        "columns": columns,
    }
    
    if constants:
        mapping["constants"] = constants
    
    return mapping
```

**Step 2: Test**

Run:
```python
python3 -c "
from mapping_tool import build_mapping
suggestions = [{'file': 'test.raw.json', 'sheet': 'P&L', 'suggestions': [
    {'source': 'Year', 'target': 'year', 'confidence': 'high'},
    {'source': 'Region', 'target': 'region_desc', 'confidence': 'high'},
    {'source': 'Unknown', 'target': None, 'confidence': 'low'},
]}]
mapping = build_mapping(suggestions, constants={'currency': 'USD'})
print(mapping)
assert mapping['columns'] == {'Year': 'year', 'Region': 'region_desc'}
assert mapping['constants'] == {'currency': 'USD'}
print('OK')
"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add mapping_tool.py
git commit -m "feat: build_mapping converts suggestions to mapping.json"
```

---

## Task 5: Implement `write_html_report()` — the review UI

**Objective:** Generate a self-contained HTML file that shows the mapping suggestions in a reviewable format with confidence indicators and sample data.

**Files:**
- Modify: `mapping_tool.py`

**Step 1: Add the HTML report function**

```python
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Mapping Review — {title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Cairo', 'Segoe UI', sans-serif; background: #1a1a2e;
         color: #e0e0e0; padding: 20px; direction: rtl; }}
  h1 {{ color: #00d4ff; margin-bottom: 10px; }}
  h2 {{ color: #ffa500; margin: 20px 0 10px; }}
  .summary {{ background: #16213e; padding: 15px; border-radius: 8px;
              margin-bottom: 20px; }}
  .summary span {{ margin-left: 20px; }}
  .high {{ color: #00ff88; }}
  .medium {{ color: #ffa500; }}
  .low {{ color: #ff4444; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px;
           background: #16213e; border-radius: 8px; overflow: hidden; }}
  th {{ background: #0f3460; color: #00d4ff; padding: 12px; text-align: right; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #2a2a4a; }}
  tr:hover {{ background: #1a2744; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 0.85em; }}
  .badge.high {{ background: #00ff8833; }}
  .badge.medium {{ background: #ffa50033; }}
  .badge.low {{ background: #ff444433; }}
  .sample {{ font-size: 0.85em; color: #888; }}
  .arrow {{ color: #00d4ff; }}
</style>
</head>
<body>
<h1>🗺️ Mapping Review Report</h1>
<p style="color:#888;margin-bottom:20px;">
  Generated: {timestamp}
</p>

{content}

<hr style="border-color:#2a2a4a;margin:30px 0;">
<p style="color:#888;font-size:0.85em;">
  Review the suggestions above. High-confidence matches (green) are likely
  correct. Medium (orange) need verification. Low/unmatched (red) require manual
  mapping. Edit the mapping.json before running map_raw_to_db.py.
</p>
</body>
</html>"""


def write_html_report(path: str, sheets: list[dict],
                      suggestions: list[dict], schema_cols: dict):
    """Write an HTML review report."""
    import datetime
    
    parts = []
    
    for sug in suggestions:
        high = sum(1 for s in sug["suggestions"] if s["confidence"] == "high")
        medium = sum(1 for s in sug["suggestions"] if s["confidence"] == "medium")
        low = sum(1 for s in sug["suggestions"] if s["confidence"] == "low" or s["target"] is None)
        
        parts.append(f"""
<div class="summary">
  <h2>📊 {sug["file"]} — Sheet: {sug["sheet"]}</h2>
  <span>Rows: <strong>{sug["n_rows"]}</strong></span>
  <span>Columns: <strong>{len(sug["suggestions"])}</strong></span>
  <span class="high">✓ High: {high}</span>
  <span class="medium">⚠ Medium: {medium}</span>
  <span class="low">✗ Low/Unmatched: {low}</span>
</div>

<table>
  <thead>
    <tr>
      <th>Source Column</th>
      <th></th>
      <th>DB Column</th>
      <th>Confidence</th>
      <th>Method</th>
    </tr>
  </thead>
  <tbody>""")
        
        for s in sug["suggestions"]:
            target = s["target"] or "—"
            badge_class = s["confidence"]
            parts.append(f"""
    <tr>
      <td><code>{s["source"]}</code></td>
      <td class="arrow">→</td>
      <td><code>{target}</code></td>
      <td><span class="badge {badge_class}">{s["confidence"]}</span></td>
      <td>{s["method"]}</td>
    </tr>""")
        
        parts.append("""
  </tbody>
</table>""")
        
        # Sample data
        if sug.get("sample_rows"):
            parts.append('<h3 style="color:#888;margin:10px 0;">Sample Data:</h3>')
            parts.append('<table><thead><tr>')
            for h in [s["source"] for s in sug["suggestions"]]:
                parts.append(f'<th>{h}</th>')
            parts.append('</tr></thead><tbody>')
            for row in sug["sample_rows"][:3]:
                parts.append('<tr>')
                for cell in row:
                    parts.append(f'<td>{cell if cell is not None else ""}</td>')
                parts.append('</tr>')
            parts.append('</tbody></table>')
    
    html = HTML_TEMPLATE.format(
        title=suggestions[0]["file"] if suggestions else "unknown",
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        content="\n".join(parts),
    )
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
```

**Step 2: Test with real data**

Run:
```bash
python3 seed_db.py --force
python3 mapping_tool.py --raw raw/ --report /tmp/mapping_review.html
# Open in browser to verify
```

Expected: HTML file created with proper RTL layout

**Step 3: Commit**

```bash
git add mapping_tool.py
git commit -m "feat: HTML review report with confidence indicators"
```

---

## Task 6: Add `test_mapping_tool.py` — comprehensive tests

**Objective:** Write tests covering all functions: scanning, matching, building, and reporting.

**Files:**
- Create: `test_mapping_tool.py`

**Step 1: Write the tests**

```python
"""
test_mapping_tool.py — tests for the mapping review tool.

Run: python3 test_mapping_tool.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

import mapping_tool as mt


def _make_raw(tmp, filename, sheet_name, headers, rows):
    """Create a fake raw JSON capture."""
    envelope = {
        "schema_version": 1,
        "document_type": "spreadsheet",
        "content": {"sheets": [{
            "name": sheet_name,
            "n_rows": len(rows) + 1,
            "cells": [headers] + rows,
        }]},
    }
    path = os.path.join(tmp, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(envelope, f)
    return path


class TestScanRawFiles(unittest.TestCase):
    def test_finds_spreadsheet_captures(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_raw(tmp, "test.raw.json", "P&L",
                      ["Year", "Region"], [[2025, "Africa"]])
            results = mt.scan_raw_files(tmp)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["headers"], ["Year", "Region"])
    
    def test_skips_non_spreadsheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            envelope = {"document_type": "pdf", "content": {}}
            with open(os.path.join(tmp, "doc.raw.json"), "w") as f:
                json.dump(envelope, f)
            results = mt.scan_raw_files(tmp)
            self.assertEqual(len(results), 0)
    
    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = mt.scan_raw_files(tmp)
            self.assertEqual(results, [])


class TestSuggestMappings(unittest.TestCase):
    def test_exact_match(self):
        sheets = [{"file": "x", "sheet": "S", "n_rows": 1,
                   "headers": ["year"], "sample_rows": []}]
        schema = {"year": "INTEGER", "region_desc": "TEXT"}
        results = mt.suggest_mappings(sheets, schema)
        s = results[0]["suggestions"][0]
        self.assertEqual(s["target"], "year")
        self.assertEqual(s["confidence"], "high")
    
    def test_arabic_match(self):
        sheets = [{"file": "x", "sheet": "S", "n_rows": 1,
                   "headers": ["المنطقة"], "sample_rows": []}]
        schema = {"year": "INTEGER", "region_desc": "TEXT"}
        results = mt.suggest_mappings(sheets, schema)
        s = results[0]["suggestions"][0]
        self.assertEqual(s["target"], "region_desc")
    
    def test_no_match(self):
        sheets = [{"file": "x", "sheet": "S", "n_rows": 1,
                   "headers": ["xyz_unknown_field"], "sample_rows": []}]
        schema = {"year": "INTEGER", "region_desc": "TEXT"}
        results = mt.suggest_mappings(sheets, schema)
        s = results[0]["suggestions"][0]
        self.assertIsNone(s["target"])
    
    def test_known_pattern_arabic(self):
        sheets = [{"file": "x", "sheet": "S", "n_rows": 1,
                   "headers": ["صافي المبيعات"], "sample_rows": []}]
        schema = {"net_sales": "REAL", "year": "INTEGER"}
        results = mt.suggest_mappings(sheets, schema)
        s = results[0]["suggestions"][0]
        self.assertEqual(s["target"], "net_sales")


class TestBuildMapping(unittest.TestCase):
    def test_basic_mapping(self):
        suggestions = [{"file": "test.raw.json", "sheet": "P&L",
                        "suggestions": [
                            {"source": "Year", "target": "year", "confidence": "high"},
                            {"source": "Region", "target": "region_desc", "confidence": "high"},
                            {"source": "X", "target": None, "confidence": "low"},
                        ]}]
        mapping = mt.build_mapping(suggestions)
        self.assertEqual(mapping["columns"], {"Year": "year", "Region": "region_desc"})
        self.assertEqual(mapping["sheet"], "P&L")
    
    def test_constants_included(self):
        suggestions = [{"file": "t.raw.json", "sheet": "S",
                        "suggestions": [
                            {"source": "Y", "target": "year", "confidence": "high"},
                        ]}]
        mapping = mt.build_mapping(suggestions, constants={"currency": "USD"})
        self.assertEqual(mapping["constants"], {"currency": "USD"})


class TestHtmlReport(unittest.TestCase):
    def test_report_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheets = [{"file": "t.raw.json", "sheet": "S", "n_rows": 5,
                       "headers": ["Year"], "sample_rows": [[2025]]}]
            suggestions = [{"file": "t.raw.json", "sheet": "S", "n_rows": 5,
                           "suggestions": [
                               {"source": "Year", "target": "year",
                                "score": 1.0, "method": "exact", "confidence": "high"},
                           ], "sample_rows": [[2025]]}]
            schema = {"year": "INTEGER"}
            path = os.path.join(tmp, "report.html")
            mt.write_html_report(path, sheets, suggestions, schema)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("Year", content)
            self.assertIn("year", content)
            self.assertIn("dir=\"rtl\"", content)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
```

**Step 2: Run the tests**

Run: `python3 test_mapping_tool.py`
Expected: All tests pass

**Step 3: Commit**

```bash
git add test_mapping_tool.py
git commit -m "test: mapping_tool comprehensive tests"
```

---

## Task 7: Wire into CI + AGENTS.md test list

**Objective:** Add the mapping_tool test to the CI pipeline and AGENTS.md test list.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `AGENTS.md`

**Step 1: Add to CI**

In `.github/workflows/ci.yml`, add after the mapper test step:

```yaml
      - name: Mapping tool tests
        run: python3 test_mapping_tool.py
```

**Step 2: Add to AGENTS.md rule 4**

Add this line to the test list:

```markdown
   - `python3 test_mapping_tool.py` — mapping review tool (auto-suggest + report)
```

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml AGENTS.md
git commit -m "ci: add mapping_tool tests to CI + AGENTS.md"
```

---

## Task 8: End-to-end test with seed data

**Objective:** Run the full pipeline: seed → extract → mapping_tool → review → load.

**Files:**
- No new files (verification only)

**Step 1: Seed and verify**

```bash
python3 seed_db.py --force
python3 mapping_tool.py --raw raw/ --report /tmp/review.html --output /tmp/test_mapping.json
```

Expected: Both files created, HTML opens correctly in browser

**Step 2: Verify the mapping is valid**

```bash
python3 map_raw_to_db.py --mapping /tmp/test_mapping.json --dry-run
```

Expected: Validation passes (or clear errors about missing required fields)

**Step 3: Final commit**

```bash
git add -A
git commit -m "docs: mapping_tool end-to-end verification complete"
git push origin mohamed/phase-2-import-workspace
```
