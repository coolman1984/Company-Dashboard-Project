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

from mapping_tool import (
    KNOWN_PATTERNS,
    _score_match,
    build_mapping,
    scan_raw_files,
    suggest_mappings,
    write_html_report,
)


class TestScanRawFiles(unittest.TestCase):
    def test_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_file = os.path.join(tmpdir, "test.raw.json")
            with open(raw_file, "w", encoding="utf-8") as handle:
                json.dump({
                    "document_type": "spreadsheet",
                    "content": {
                        "sheets": [{
                            "name": "Sheet1",
                            "cells": [
                                ["Year", "Region", "Sales"],
                                ["2025", "Africa", 1000],
                                ["2026", "Europe", 2000],
                            ],
                            "n_rows": 100,
                        }]
                    },
                }, handle)

            results = scan_raw_files(tmpdir)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["file"], "test.raw.json")
            self.assertEqual(results[0]["sheet"], "Sheet1")
            self.assertEqual(results[0]["headers"], ["Year", "Region", "Sales"])
            self.assertEqual(results[0]["n_rows"], 100)
            self.assertEqual(len(results[0]["sample_rows"]), 2)

    def test_skips_non_spreadsheet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_file = os.path.join(tmpdir, "test.raw.json")
            with open(raw_file, "w", encoding="utf-8") as handle:
                json.dump({"document_type": "pdf", "content": {}}, handle)
            self.assertEqual(scan_raw_files(tmpdir), [])

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(scan_raw_files(tmpdir), [])


class TestScoreMatch(unittest.TestCase):
    def test_exact(self):
        score, method = _score_match("year", "year")
        self.assertEqual(score, 1.0)
        self.assertEqual(method, "exact")

    def test_known_pattern(self):
        score, method = _score_match("المنطقة", "region_desc")
        self.assertEqual(score, 0.9)
        self.assertEqual(method, "known_pattern")

        score, method = _score_match("صافي المبيعات", "net_sales")
        self.assertEqual(score, 0.9)
        self.assertEqual(method, "known_pattern")

    def test_normalized_arabic_variants(self):
        score, method = _score_match("إدارة", "ادارة")
        self.assertEqual(score, 0.7)
        self.assertEqual(method, "normalized")

    def test_substring(self):
        score, method = _score_match("sales_amount", "sales")
        self.assertEqual(score, 0.5)
        self.assertEqual(method, "substring")

        score, method = _score_match("gross_sales_amount", "gross_sales")
        self.assertEqual(score, 0.5)
        self.assertEqual(method, "substring")

    def test_none(self):
        score, method = _score_match("unknown_field", "year")
        self.assertEqual(score, 0.0)
        self.assertEqual(method, "none")


class TestSuggestMappings(unittest.TestCase):
    def test_basic(self):
        sheets = [{
            "file": "test.raw.json",
            "sheet": "Sheet1",
            "headers": ["Year", "المنطقة", "Sales", "Unknown"],
            "n_rows": 100,
            "sample_rows": [],
        }]
        schema = {"year": "INTEGER", "region_desc": "TEXT", "net_sales": "REAL"}
        suggestions = suggest_mappings(sheets, schema)
        mappings = {s["source"]: s for s in suggestions[0]["suggestions"]}

        self.assertEqual(mappings["Year"]["target"], "year")
        self.assertEqual(mappings["Year"]["confidence"], "high")
        self.assertEqual(mappings["المنطقة"]["target"], "region_desc")
        self.assertEqual(mappings["المنطقة"]["confidence"], "high")
        self.assertEqual(mappings["Sales"]["target"], "net_sales")
        self.assertIn(mappings["Sales"]["confidence"], ("high", "medium"))
        self.assertIsNone(mappings["Unknown"]["target"])
        self.assertEqual(mappings["Unknown"]["confidence"], "low")

    def test_empty_headers(self):
        sheets = [{
            "file": "test.raw.json",
            "sheet": "Sheet1",
            "headers": [],
            "n_rows": 0,
            "sample_rows": [],
        }]
        suggestions = suggest_mappings(sheets, {})
        self.assertEqual(suggestions[0]["suggestions"], [])


class TestBuildMapping(unittest.TestCase):
    def test_basic(self):
        sheets = [{
            "file": "test.raw.json",
            "sheet": "Sheet1",
            "headers": ["Year", "Region"],
            "n_rows": 100,
            "sample_rows": [],
        }]
        schema = {"year": "INTEGER", "region_desc": "TEXT"}
        mapping = build_mapping(suggest_mappings(sheets, schema))

        self.assertIn("source_glob", mapping)
        self.assertEqual(mapping["sheet"], "Sheet1")
        self.assertEqual(mapping["header_row"], 0)
        self.assertEqual(mapping["columns"]["Year"], "year")
        self.assertEqual(mapping["columns"]["Region"], "region_desc")

    def test_constants(self):
        sheets = [{
            "file": "test.raw.json",
            "sheet": "Sheet1",
            "headers": ["Year"],
            "n_rows": 100,
            "sample_rows": [],
        }]
        mapping = build_mapping(
            suggest_mappings(sheets, {"year": "INTEGER"}),
            constants={"company_id": "ACME"},
        )
        self.assertEqual(mapping["constants"], {"company_id": "ACME"})

    def test_skips_low_confidence(self):
        sheets = [{
            "file": "test.raw.json",
            "sheet": "Sheet1",
            "headers": ["Year", "UnknownField"],
            "n_rows": 100,
            "sample_rows": [],
        }]
        mapping = build_mapping(suggest_mappings(sheets, {"year": "INTEGER"}))
        self.assertIn("Year", mapping["columns"])
        self.assertNotIn("UnknownField", mapping["columns"])


class TestHtmlReport(unittest.TestCase):
    def test_report_generated(self):
        sheets = [{
            "file": "test.raw.json",
            "sheet": "Sheet1",
            "headers": ["Year", "Region"],
            "n_rows": 100,
            "sample_rows": [["2025", "Africa"], ["2026", "Europe"]],
        }]
        schema = {"year": "INTEGER", "region_desc": "TEXT"}
        suggestions = suggest_mappings(sheets, schema)

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "report.html")
            write_html_report(report_path, sheets, suggestions, schema)
            self.assertTrue(os.path.exists(report_path))
            self.assertGreater(os.path.getsize(report_path), 0)
            with open(report_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Year", content)
            self.assertIn("year", content)
            self.assertIn("Region", content)
            self.assertIn("region_desc", content)
            self.assertIn('dir="rtl"', content)
            self.assertIn("High:", content)


class TestKnownPatterns(unittest.TestCase):
    def test_coverage(self):
        required_patterns = [
            "year", "version", "period", "region", "country", "customer",
            "net sales", "gross margin", "operating profit", "net income",
        ]
        for pattern in required_patterns:
            self.assertTrue(
                pattern in KNOWN_PATTERNS or pattern.replace(" ", "_") in KNOWN_PATTERNS,
                pattern,
            )


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
