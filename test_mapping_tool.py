"""
Tests for mapping_tool.py
"""
import json
import os
import tempfile
import pytest

from mapping_tool import (
    scan_raw_files,
    suggest_mappings,
    build_mapping,
    write_html_report,
    _score_match,
    KNOWN_PATTERNS
)


def test_scan_raw_files_basic():
    """Test scanning raw JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_file = os.path.join(tmpdir, 'test.raw.json')
        # Use the actual raw.json structure: cells is array of arrays
        with open(raw_file, 'w') as f:
            json.dump({
                'document_type': 'spreadsheet',
                'content': {
                    'sheets': [{
                        'name': 'Sheet1',
                        'cells': [
                            ['Year', 'Region', 'Sales'],  # header row
                            ['2025', 'Africa', 1000],
                            ['2026', 'Europe', 2000]
                        ],
                        'n_rows': 100
                    }]
                }
            }, f)
        
        results = scan_raw_files(tmpdir)
        assert len(results) == 1
        assert results[0]['file'] == 'test.raw.json'
        assert results[0]['sheet'] == 'Sheet1'
        assert results[0]['headers'] == ['Year', 'Region', 'Sales']
        assert results[0]['n_rows'] == 100
        assert len(results[0]['sample_rows']) == 2


def test_scan_raw_files_skips_non_spreadsheet():
    """Test that non-spreadsheet files are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_file = os.path.join(tmpdir, 'test.raw.json')
        with open(raw_file, 'w') as f:
            json.dump({'document_type': 'pdf', 'content': {}}, f)
        
        results = scan_raw_files(tmpdir)
        assert len(results) == 0


def test_scan_raw_files_empty_folder():
    """Test scanning an empty folder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        results = scan_raw_files(tmpdir)
        assert len(results) == 0


def test_score_match_exact():
    """Test exact string matching."""
    score, method = _score_match('year', 'year')
    assert score == 1.0
    assert method == 'exact'


def test_score_match_known_pattern():
    """Test known pattern matching."""
    score, method = _score_match('المنطقة', 'region_desc')
    assert score == 0.9
    assert method == 'known_pattern'
    
    score, method = _score_match('صافي المبيعات', 'net_sales')
    assert score == 0.9
    assert method == 'known_pattern'


def test_score_match_normalized():
    """Test normalized matching (Arabic variants)."""
    # Arabic-to-Arabic normalized match
    score, method = _score_match('منطقة', 'منطقة')  # exact match after normalization
    assert score == 1.0
    assert method == 'exact'
    
    # Test Arabic variant matching (alef variants)
    score, method = _score_match('إدارة', 'ادارة')  # alef with hamza vs plain alef
    assert score == 0.7
    assert method == 'normalized'


def test_score_match_fuzzy():
    """Test fuzzy substring matching."""
    score, method = _score_match('sales_amount', 'sales')
    assert score == 0.5  # substring match gives 0.5
    assert method == 'substring'
    
    # Another substring example - 'gross sales' is found in 'gross_sales_amount'
    score, method = _score_match('gross_sales_amount', 'gross_sales')
    assert score == 0.5
    assert method == 'substring'


def test_score_match_none():
    """Test no match."""
    score, method = _score_match('unknown_field', 'year')
    assert score == 0.0
    assert method == 'none'


def test_suggest_mappings_basic():
    """Test basic mapping suggestions."""
    sheets = [{
        'file': 'test.raw.json',
        'sheet': 'Sheet1',
        'headers': ['Year', 'المنطقة', 'Sales', 'Unknown'],
        'n_rows': 100,
        'sample_rows': []
    }]
    
    schema = {'year': 'INTEGER', 'region_desc': 'TEXT', 'net_sales': 'REAL'}
    suggestions = suggest_mappings(sheets, schema)
    
    assert len(suggestions) == 1
    assert suggestions[0]['sheet'] == 'Sheet1'
    
    # Check individual mappings
    mappings = {s['source']: s for s in suggestions[0]['suggestions']}
    
    assert mappings['Year']['target'] == 'year'
    assert mappings['Year']['confidence'] == 'high'
    
    assert mappings['المنطقة']['target'] == 'region_desc'
    assert mappings['المنطقة']['confidence'] == 'high'
    
    assert mappings['Sales']['target'] == 'net_sales'
    assert mappings['Sales']['confidence'] in ['high', 'medium']
    
    assert mappings['Unknown']['target'] is None
    assert mappings['Unknown']['confidence'] == 'low'


def test_suggest_mappings_empty_headers():
    """Test with empty headers."""
    sheets = [{
        'file': 'test.raw.json',
        'sheet': 'Sheet1',
        'headers': [],
        'n_rows': 0,
        'sample_rows': []
    }]
    
    suggestions = suggest_mappings(sheets, {})
    assert len(suggestions[0]['suggestions']) == 0


def test_build_mapping_basic():
    """Test building a mapping JSON."""
    sheets = [{
        'file': 'test.raw.json',
        'sheet': 'Sheet1',
        'headers': ['Year', 'Region'],
        'n_rows': 100,
        'sample_rows': []
    }]
    
    schema = {'year': 'INTEGER', 'region_desc': 'TEXT'}
    suggestions = suggest_mappings(sheets, schema)
    mapping = build_mapping(suggestions)
    
    assert 'source_glob' in mapping
    assert 'sheet' in mapping
    assert 'columns' in mapping
    assert 'header_row' in mapping
    assert mapping['sheet'] == 'Sheet1'
    assert mapping['header_row'] == 0
    
    # Check columns
    assert mapping['columns']['Year'] == 'year'
    assert mapping['columns']['Region'] == 'region_desc'


def test_build_mapping_with_constants():
    """Test building a mapping with constants."""
    sheets = [{
        'file': 'test.raw.json',
        'sheet': 'Sheet1',
        'headers': ['Year'],
        'n_rows': 100,
        'sample_rows': []
    }]
    
    schema = {'year': 'INTEGER'}
    suggestions = suggest_mappings(sheets, schema)
    mapping = build_mapping(suggestions, constants={'company_id': 'ACME'})
    
    assert 'constants' in mapping
    assert mapping['constants']['company_id'] == 'ACME'


def test_build_mapping_skips_low_confidence():
    """Test that low confidence mappings are skipped."""
    sheets = [{
        'file': 'test.raw.json',
        'sheet': 'Sheet1',
        'headers': ['Year', 'UnknownField'],
        'n_rows': 100,
        'sample_rows': []
    }]
    
    schema = {'year': 'INTEGER'}
    suggestions = suggest_mappings(sheets, schema)
    mapping = build_mapping(suggestions)
    
    assert 'Year' in mapping['columns']
    assert 'UnknownField' not in mapping['columns']


def test_write_html_report():
    """Test HTML report generation."""
    sheets = [{
        'file': 'test.raw.json',
        'sheet': 'Sheet1',
        'headers': ['Year', 'Region'],
        'n_rows': 100,
        'sample_rows': [
            ['2025', 'Africa'],
            ['2026', 'Europe']
        ]
    }]
    
    schema = {'year': 'INTEGER', 'region_desc': 'TEXT'}
    suggestions = suggest_mappings(sheets, schema)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = os.path.join(tmpdir, 'report.html')
        write_html_report(report_path, sheets, suggestions, schema)
        
        assert os.path.exists(report_path)
        assert os.path.getsize(report_path) > 0
        
        with open(report_path, 'r') as f:
            content = f.read()
        
        # Check HTML structure
        assert 'Year' in content
        assert 'year' in content
        assert 'Region' in content
        assert 'region_desc' in content
        assert 'dir="rtl"' in content
        assert 'High:' in content


def test_known_patterns_coverage():
    """Test that known patterns cover common fields."""
    required_patterns = [
        'year', 'version', 'period', 'region', 'country', 'customer',
        'net sales', 'gross margin', 'operating profit', 'net income'
    ]
    
    for pattern in required_patterns:
        assert pattern in KNOWN_PATTERNS or pattern.replace(' ', '_') in KNOWN_PATTERNS


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
