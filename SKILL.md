---
name: company-dashboard
description: Full-stack financial analysis platform that extracts PL data from Excel via COM automation, stores 790K+ records in SQLite, pre-computes all dashboard data as static JSON, and serves an interactive drill-down dashboard with instant API responses. Use for building, extending, or troubleshooting the PL analysis pipeline.
version: "2.0"
last-updated: "2026-06-08"
---

# Company Dashboard — PL Financial Analysis Platform

> **Living Document**: This SKILL.md is the master reference for the entire PL analysis system. Update it whenever the pipeline, database, server, or dashboard changes.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Data Pipeline](#data-pipeline)
4. [Database Schema](#database-schema)
5. [Pre-Computed Data Layer](#pre-computed-data-layer)
6. [Server API Reference](#server-api-reference)
7. [Dashboard Features](#dashboard-features)
8. [Step-by-Step Build Guide](#step-by-step-build-guide)
9. [Troubleshooting](#troubleshooting)
10. [File Structure](#file-structure)
11. [Performance Benchmarks](#performance-benchmarks)
12. [Future Enhancements](#future-enhancements)
13. [Change Log](#change-log)

---

## System Overview

A complete financial analysis platform that:

1. **Extracts** data from `PL 2022~2026.xlsb` using Excel COM automation
2. **Stores** 790,245 detail records in a high-performance SQLite database
3. **Pre-computes** all dashboard data as 133 static JSON files (eliminates query latency)
4. **Serves** data via a Node.js API server with instant in-memory responses
5. **Visualizes** via an interactive 4-tab dashboard with Chart.js

### Key Metrics

| Metric | Value |
|--------|-------|
| Source file | `PL 2022~2026.xlsb` (Excel Binary) |
| Sheet1 rows | 790,245 |
| Sheet1 columns | 59 (A through BG) |
| Sheet3 pivot rows | 17 (summary P&L) |
| Database size | ~362 MB |
| Indexes | 12 |
| Views | 6 |
| Pre-computed JSON files | 312 |
| API endpoints | 13 |
| Dashboard tabs | 4 |
| API response time | **2-35ms** (was 1-5s with Python subprocess) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser Dashboard                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │PL Overview│ │ Regional │ │ Product  │ │  Variance    │  │
│  │  Tab      │ │ Analysis │ │ Analysis │ │  Drill-Down  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│         │            │            │              │           │
│         └────────────┴────────────┴──────────────┘         │
│                       │ fetch() + client-side cache         │
└───────────────────────┼─────────────────────────────────────┘
                        │ HTTP :3001 (instant responses)
┌───────────────────────┼─────────────────────────────────────┐
│              Node.js Server (server.js) v2                    │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │        In-Memory JSON Cache (133 files loaded)        │  │
│  │  summary, yearly-pl, regional-pl, mgroup-pl,         │  │
│  │  country-pl, customer-pl, yoy-variance,              │  │
│  │  drilldown_*, top_products_*                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                       │ fs.readFileSync at startup          │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │           api_data/ directory (133 JSON files)         │  │
│  └───────────────────────────────────────────────────────┘  │
│                       │ python precompute_data.py           │
└───────────────────────┼─────────────────────────────────────┘
                        │ SQL queries (one-time batch)
┌───────────────────────▼─────────────────────────────────────┐
│              SQLite Database (pl_detail.db)                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  pl_detail table (790,245 rows × 59 columns)           │ │
│  │  + 12 indexes + 6 views                                │ │
│  └─────────────────────────────────────────────────────────┘ │
│  Source: PL 2022~2026.xlsb → COM Excel → chunked ingest     │
└──────────────────────────────────────────────────────────────┘
```

### Key Architecture Decision: Pre-Computed Static Backend (v2)

**Problem**: v1 used Python subprocess for every API call (1-5 seconds per query). This made the dashboard feel sluggish and some drill-down choices didn't work (timeout).

**Solution**: v2 pre-computes ALL possible dashboard queries as static JSON files at data-refresh time. The server loads all files into memory at startup and serves them with `JSON.stringify()` — no database queries at request time.

**Result**: API responses went from 1-5 seconds to 2-35ms (100-1000x faster).

---

## Data Pipeline

### Step 1: Explore Source Data

**Script**: `explore_sheet1.py`

Uses Excel COM to read headers and sample rows from Sheet1 to understand the data structure before ingestion.

```python
# Key COM pattern:
excel = win32com.client.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
workbook = excel.Workbooks.Open(file_path, ReadOnly=True)
sheet = workbook.Sheets(2)  # Sheet1 is the 2nd sheet

# Read header row only (fast)
header_range = sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, cols))
headers = header_range.Value[0]  # 0-indexed tuple
```

**What we discovered**:
- Sheet1: 790,246 rows × 59 columns (A through BG)
- Sheet3 (named "Sheet3"): 42 rows × 33 columns (pivot summary)
- 3 versions: Actual, T06, T07
- 5 years: 2022-2026
- 11 regions: Africa, Australia, CIS, China, Europe, Korea, Latin, M/East, S.E.Asia, S.W.Asia, USA
- 3 classes: Direct customer, Domestic, HQ
- 150+ product groups

### Step 2: Extract Pivot Summary (Sheet3)

**Script**: `extract_pl_data.py`

Reads the first pivot table from Sheet3 (the summary view) and saves to `pl_data.json`.

```python
# Read entire used range in bulk
used_range = target_sheet.UsedRange
data = used_range.Value  # Returns 0-indexed tuple of tuples

# Process: win32com returns 0-indexed tuples for 2D ranges
for r in range(len(data)):
    for c in range(len(data[r])):
        val = data[r][c] if data[r][c] is not None else ""
```

### Step 3: Ingest Detail Data (Sheet1) into SQLite

**Script**: `ingest_sheet1.py`

The main ingestion pipeline. Reads 10,000 rows at a time via COM and bulk-inserts into SQLite.

#### Column Mapping (59 columns)

| # | Excel Col | DB Column | Type | Description |
|---|-----------|-----------|------|-------------|
| 1 | A | class | TEXT | Customer class (Direct/Domestic/HQ) |
| 2 | B | region_desc | TEXT | Region name |
| 3 | C | country_name | TEXT | Country name |
| 4 | D | customer_name | TEXT | Customer name |
| 5 | E | m_group_desc | TEXT | Product group |
| 6 | F | year | INTEGER | Fiscal year |
| 7 | G | class_code | TEXT | Class code |
| 8 | H | version | TEXT | Actual/T06/T07 |
| 9-16 | I-P | product_number through currency | TEXT/REAL | Identifiers |
| 17-19 | Q-S | qty_gross/return/net | REAL | Quantities |
| 20-26 | T-Z | s_rrp through s_special_margin | REAL | Sales pricing |
| 27-36 | AA-AJ | s_gross_sales through s_fob_sales_amt | REAL | Sales amounts |
| 37-43 | AK-AQ | sales_deduction through s_sale_deduction_tax | REAL | Deductions |
| 44 | AR | net_sales | REAL | **Net Sales** |
| 45 | AS | cost_of_goods_sold | REAL | **COGS** |
| 46 | AT | material_cost | REAL | Material cost |
| 47 | AU | gross_margin | REAL | **Gross Margin** |
| 48 | AV | operating_expense | REAL | **Operating Expense** |
| 49 | AW | sales_expense | REAL | Sales expense |
| 50 | AX | operating_profit | REAL | **Operating Profit** |
| 51 | AY | profit_before_tax | REAL | Profit before tax |
| 52-53 | AZ-BA | corporate_tax / corp_tax | REAL | Tax |
| 54 | BB | net_income | REAL | **Net Income** |
| 55-59 | BC-BG | sa_hq_sales_comm through sa_royalty_hq | REAL | Royalties |

#### Chunked Ingestion Strategy

```python
CHUNK_SIZE = 10000  # Rows per COM read + DB insert

for chunk_idx in range(num_chunks):
    chunk_range = sheet.Range(sheet.Cells(chunk_start, 1), sheet.Cells(chunk_end, total_cols))
    chunk_data = chunk_range.Value
    rows_to_insert = []
    for r in range(len(chunk_data)):
        row = [chunk_data[r][c] if chunk_data[r][c] is not None else None for c in range(len(chunk_data[r]))]
        rows_to_insert.append(tuple(row))
    cursor.executemany(insert_sql, rows_to_insert)
    conn.commit()
```

**Performance**: ~790K rows ingested in ~3-5 minutes

### Step 4: Create Indexes and Views

**Script**: `create_indexes_views.py`

Indexes are created AFTER all data is loaded (much faster than incremental indexing).

#### Indexes (12 total)

| Index Name | Column(s) | Purpose |
|-----------|-----------|---------|
| idx_year | year | Filter by year |
| idx_region | region_desc | Filter by region |
| idx_country | country_name | Filter by country |
| idx_customer | customer_name | Filter by customer |
| idx_mgroup | m_group_desc | Filter by product group |
| idx_class | class | Filter by class |
| idx_version | version | Filter Actual vs Budget |
| idx_period | period | Filter by period |
| idx_profit_center | profit_center | Filter by profit center |
| idx_product | product_number | Filter by product |
| idx_year_region | year, region_desc | Compound: year + region |
| idx_year_mgroup | year, m_group_desc | Compound: year + product group |
| idx_year_customer | year, customer_name | Compound: year + customer |

#### Views (6 total)

1. **v_yearly_pl** — Yearly P&L summary (Actual only)
2. **v_regional_pl** — P&L by year × region
3. **v_mgroup_pl** — P&L by year × product group
4. **v_country_pl** — P&L by year × region × country
5. **v_customer_pl** — P&L by year × customer × region
6. **v_yoy_variance** — Year-over-year variance with $ and % changes

### Step 5: Pre-Compute Dashboard Data

**Script**: `precompute_data.py`

Runs all dashboard queries once and saves results as JSON files in `api_data/` directory. This is the key performance optimization.

**When to run**: After database creation or data refresh. Must be re-run if the source data changes.

```bash
python precompute_data.py
# Output: 133 files in api_data/ directory (~114 seconds)
```

---

## Pre-Computed Data Layer

### Overview

All dashboard data is pre-computed as static JSON files. The server loads these into memory at startup and serves them instantly — no database queries at request time.

### File Categories

| Category | Files | Description |
|----------|-------|-------------|
| Summary | 1 | Database summary (row count, distinct values) |
| Yearly PL | 1 | 5 rows (one per year) |
| Regional PL | 1 | 47 rows (11 regions × 5 years) |
| Product Group PL | 1 | 560 rows (112 groups × 5 years) |
| Country PL | 1 | 360 rows (72 countries × 5 years) |
| Customer PL | 1 | 250 rows (top 50 per year) |
| YoY Variance | 1 | 5 rows (one per year pair) |
| Drill-down | 300 | 5 dims × 6 metrics × 10 year pairs (ALL combinations) |
| Top Products | 5 | Top 30 per year |
| **Total** | **312** | |

### Drill-Down File Naming Convention

```
drilldown_{dimension}_{metric}_{year1}_{year2}.json
```

Examples:
- `drilldown_region_desc_net_sales_2024_2025.json`
- `drilldown_customer_name_gross_margin_2023_2024.json`
- `drilldown_m_group_desc_operating_profit_2025_2026.json`

### Adding New Pre-Computed Data

1. Add the query to `precompute_data.py`
2. Run `python precompute_data.py`
3. Add the API endpoint to `server.js` (read from `cache[key]`)
4. Restart the server

---

## Database Schema

```sql
CREATE TABLE pl_detail (
    class TEXT,
    region_desc TEXT,
    country_name TEXT,
    customer_name TEXT,
    m_group_desc TEXT,
    year INTEGER,
    class_code TEXT,
    version TEXT,           -- 'Actual', 'T06', 'T07'
    product_number TEXT,
    sender_ba TEXT,
    customer_code TEXT,
    country_code TEXT,
    profit_center TEXT,
    valuation_class REAL,
    period REAL,
    currency TEXT,
    qty_gross REAL, qty_return REAL, qty_net REAL,
    s_rrp REAL, reference_price REAL, dealer_discount REAL,
    s_base_margin REAL, s_contract_margin REAL,
    s_additional_margin REAL, s_special_margin REAL,
    s_gross_sales REAL, s_gross_sales_amt REAL,
    s_other_sales REAL, s_oth_sales_tax_inc REAL,
    s_internal_sales_amt REAL, s_return_amt REAL,
    s_return_amt_alt REAL, ref_sales REAL, s_ifc REAL,
    s_fob_sales_amt REAL,
    sales_deduction REAL, s_sales_allowance REAL,
    s_rebate REAL, s_cash_discount REAL, s_price_protection REAL,
    s_coop REAL, s_sale_deduction_tax REAL,
    net_sales REAL,          -- ★ Key P&L metric
    cost_of_goods_sold REAL, -- ★ Key P&L metric
    material_cost REAL,
    gross_margin REAL,       -- ★ Key P&L metric
    operating_expense REAL,  -- ★ Key P&L metric
    sales_expense REAL,
    operating_profit REAL,   -- ★ Key P&L metric
    profit_before_tax REAL,
    corporate_tax REAL, corp_tax REAL,
    net_income REAL,         -- ★ Key P&L metric
    sa_hq_sales_comm REAL, sa_corp_promotion REAL,
    royalty REAL, sa_royalty_3rd_party REAL, sa_royalty_hq REAL
);
```

### Key Dimensions

| Dimension | Column | Distinct Values |
|-----------|--------|----------------|
| Year | `year` | 2022, 2023, 2024, 2025, 2026 |
| Version | `version` | Actual, T06, T07 |
| Region | `region_desc` | 11 regions |
| Country | `country_name` | ~50+ countries |
| Customer | `customer_name` | ~100+ customers |
| Product Group | `m_group_desc` | 150+ groups |
| Class | `class` | Direct customer, Domestic, HQ |

---

## Server API Reference

**Base URL**: `http://localhost:3001`

### Endpoints

| Endpoint | Method | Description | Parameters | Response Time |
|----------|--------|-------------|-----------|---------------|
| `/api/summary` | GET | Database summary & filter options | — | ~11ms |
| `/api/data-freshness` | GET | Period coverage by year and version | — | ~5ms |
| `/api/yearly-pl` | GET | Yearly P&L summary (Actual) | — | ~5ms |
| `/api/regional-pl` | GET | P&L by year × region | — | ~8ms |
| `/api/mgroup-pl` | GET | P&L by year × product group | — | ~35ms |
| `/api/country-pl` | GET | P&L by year × country | `?region=X` | ~15ms |
| `/api/customer-pl` | GET | P&L by year × customer | `?year=X&limit=N` | ~10ms |
| `/api/yoy-variance` | GET | Year-over-year variance | — | ~5ms |
| `/api/drilldown` | GET | Variance drill-down | `?dimension=X&year1=X&year2=X&metric=X` | **~2ms** |
| `/api/top-products` | GET | Top products per year | `?year=X` | ~3ms |
| `/api/status` | GET | Server status & cache info | — | ~2ms |

### Drill-Down Parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `dimension` | `region_desc`, `country_name`, `m_group_desc`, `customer_name`, `class` | Grouping dimension |
| `year1` | 2022-2026 | From year |
| `year2` | 2022-2026 | To year |
| `metric` | `net_sales`, `cost_of_goods_sold`, `gross_margin`, `operating_expense`, `operating_profit`, `net_income` | P&L metric to analyze |

### Example Queries

```bash
# Yearly P&L
curl http://localhost:3001/api/yearly-pl

# Regional Net Sales drill-down 2024→2025 (instant: ~2ms)
curl "http://localhost:3001/api/drilldown?dimension=region_desc&year1=2024&year2=2025&metric=net_sales"

# Top 20 customers in 2025
curl "http://localhost:3001/api/customer-pl?year=2025&limit=20"

# Server status
curl http://localhost:3001/api/status
```

### Query Backend

**v2 (current)**: All data served from in-memory JSON cache. No database queries at request time. No Python subprocess.

**v1 (deprecated)**: Used Python subprocess for every API call (1-5 seconds per query). Removed in v2.

---

## Dashboard Features

### Tab 1: PL Overview (instant — embedded data)

- **6 KPI Cards**: Net Sales, Gross Margin, Operating Profit, Net Income, Revenue CAGR, Gross Margin %
- **Revenue & Cost Trend Chart**: Grouped bar (Net Sales, COGS, Gross Margin)
- **Margin Analysis Chart**: Line chart (Gross Margin %, Operating Margin %, Net Income %)
- **Net Income Chart**: Bar chart with green/red coloring
- **Cost Structure Chart**: COGS %, OpEx %, Overhead % of Net Sales
- **Detailed P&L Table**: All line items × 5 years + YoY variance columns

### Tab 2: Regional Analysis (lazy-loaded, client-cached)

- **Metric selector**: Switch between Net Sales, COGS, Gross Margin, Operating Profit, Net Income
- **Regional Comparison Chart**: Grouped bars by region × year
- **Regional Detail Table**: All regions × all years
- **Client-side caching**: Data fetched once, metric changes re-render from cache instantly

### Tab 3: Product Analysis (lazy-loaded, client-cached)

- **Year selectors**: Compare any 2 years side-by-side
- **Top 15 Product Groups Chart**: Horizontal bar with year comparison
- **Gross Margin % Chart**: Margin analysis by product group
- **Product Detail Table**: Net Sales, change $, change %, GM%, Opx%
- **Client-side caching**: mgroup-pl data fetched once, year/metric changes re-render from cache

### Tab 4: Variance Drill-Down (pre-computed, instant)

- **4 selectors**: Year1, Year2, Dimension, Metric
- **Validation**: Year1 ≠ Year2 check, loading state on button
- **Variance Waterfall Chart**: Top 20 contributors to change
- **Variance Detail Table**: Sorted by absolute impact with visual impact bars
- **Toast notifications**: Success/error feedback on drill-down

### Dashboard Best Practices

1. **Lazy Loading**: Tab data is only fetched when the tab is first visited
2. **Client-Side Caching**: Regional and product data is cached after first fetch; metric/year changes re-render from cache
3. **Error Handling**: All fetches use `safeFetch()` with timeout (10s) and error toast notifications
4. **Button States**: Drill-down button shows "Loading..." and disables during fetch
5. **Input Validation**: Year1 ≠ Year2 check before drill-down
6. **Separated JS**: Dashboard logic in `app.js`, HTML in `index.html` — easier to maintain

---

## Step-by-Step Build Guide

### Prerequisites

- Windows with Microsoft Excel installed
- Python 3.x with `pywin32` (`pip install pywin32`)
- Node.js 18+

### Step 1: Explore the Excel File

```bash
python explore_sheet1.py
```

### Step 2: Extract Pivot Summary

```bash
python extract_pl_data.py
```

### Step 3: Ingest Detail Data

```bash
python ingest_sheet1.py
```

**This takes 3-5 minutes** for 790K rows. If interrupted:
- Kill Excel: `taskkill /F /IM EXCEL.EXE`
- Delete partial database: `del pl_detail.db`
- Re-run

### Step 4: Create Indexes and Views

```bash
python create_indexes_views.py
```

Takes ~10-15 seconds. Safe to re-run.

### Step 5: Pre-Compute Dashboard Data

```bash
python precompute_data.py
```

Takes ~2 minutes. Creates 133 JSON files in `api_data/`. **Must re-run after any data refresh.**

### Step 6: Start the Server

```bash
node server.js
```

Server starts on `http://localhost:3001`. Verify:
```bash
curl http://localhost:3001/api/status
```

### Step 7: Open the Dashboard

Open `http://localhost:3001` in a browser.

---

## Troubleshooting

### COM Excel Issues

| Problem | Solution |
|---------|----------|
| `RPC server unavailable` | Kill Excel: `taskkill /F /IM EXCEL.EXE` |
| Script hangs | Excel may be showing a dialog. Kill and retry with `DisplayAlerts = False` |
| `IndexError: tuple index out of range` | win32com returns 0-indexed tuples. Use `data[r][c]` not `data[r+1][c+1]` |
| `UnicodeEncodeError` | Windows console can't print Unicode. Use ASCII alternatives |
| Sheet not found | Sheet3 is Sheets(1), Sheet1 is Sheets(2) |

### Database Issues

| Problem | Solution |
|---------|----------|
| Database locked | Close connections, delete `-wal` and `-shm` files |
| Slow queries | Verify indexes: `SELECT name FROM sqlite_master WHERE type='index'` |
| Views missing | Run `create_indexes_views.py` |

### Server Issues

| Problem | Solution |
|---------|----------|
| Port in use | `taskkill /F /IM node.exe` |
| `api_data/ not found` | Run `python precompute_data.py` first |
| API returns 404 for drill-down | Specific combination not pre-computed. Run `python precompute_data.py` |
| Slow responses | Should be 2-35ms. If slow, check server console for errors |

### Dashboard Issues

| Problem | Solution |
|---------|----------|
| Charts not loading | Check browser console. Chart.js loads from CDN — needs internet |
| Regional/Product tabs empty | Server must be running on port 3001 |
| Drill-down shows no data | Ensure year1 ≠ year2 and data exists for both years |
| `app.js` not loading | Check browser console for 404. File must be in same directory as `index.html` |

---

## File Structure

```
Company Dashboard/
├── SKILL.md                  ← This documentation (master reference)
├── PL 2022~2026.xlsb         ← Source Excel file (binary, DO NOT MODIFY)
├── pl_detail.db              ← SQLite database (362 MB, 790K rows)
├── pl_data.json              ← Sheet3 pivot summary (extracted)
│
├── explore_sheet1.py         ← Step 1: Explore data structure
├── extract_pl_data.py        ← Step 2: Extract pivot summary
├── ingest_sheet1.py          ← Step 3: Ingest 790K rows into SQLite
├── create_indexes_views.py   ← Step 4: Create indexes and views
├── precompute_data.py        ← Step 5: Pre-compute all dashboard data as JSON
│
├── server.js                 ← Step 6: Node.js API server v2 (static JSON backend)
├── index.html                ← Step 7: Dashboard HTML
├── app.js                    ← Step 7: Dashboard JavaScript (separated from HTML)
├── package.json              ← Node scripts and dependencies
├── smoke_test.js             ← API, metadata, and static-file security smoke tests
│
├── api_data/                 ← Pre-computed JSON files (133 files)
│   ├── summary.json
│   ├── yearly-pl.json
│   ├── regional-pl.json
│   ├── mgroup-pl.json
│   ├── country-pl.json
│   ├── customer-pl.json
│   ├── yoy-variance.json
│   ├── drilldown_*.json      ← 120 drill-down files
│   └── top_products_*.json   ← 5 top product files
│
├── check_db.py               ← Utility: Check row count and size
└── verify_db.py              ← Utility: Verify views and indexes
```

---

## Performance Benchmarks

### API Response Times (v2 vs v1)

| Endpoint | v1 (Python subprocess) | v2 (Pre-computed JSON) | Speedup |
|----------|----------------------|----------------------|---------|
| `/api/summary` | ~1,500ms | ~11ms | **136x** |
| `/api/regional-pl` | ~2,000ms | ~8ms | **250x** |
| `/api/mgroup-pl` | ~3,000ms | ~35ms | **86x** |
| `/api/drilldown` | ~3,500ms | **~2ms** | **1,750x** |
| `/api/yoy-variance` | ~1,200ms | ~5ms | **240x** |

### Pre-Computation Cost

| Operation | Time |
|-----------|------|
| `precompute_data.py` (133 files) | ~114 seconds |
| Server startup (load 133 files) | <1 second |
| Total JSON size | ~450 KB |

---

## Future Enhancements

- [ ] **DuckDB Migration**: When network allows, install `duckdb` for faster pre-computation
- [ ] **better-sqlite3**: Install native Node.js SQLite binding for dynamic queries
- [ ] **Period-Level Analysis**: Drill down by period (month/quarter) within a year
- [ ] **Budget vs Actual**: Compare version='Actual' vs 'T06'/'T07' for variance analysis
- [ ] **Customer Deep-Dive**: Dedicated customer profitability analysis page
- [ ] **Export to Excel**: Generate Excel reports from the dashboard
- [ ] **Trend Forecasting**: Simple linear regression for 2027 projections
- [ ] **Waterfall Chart**: True waterfall (not just grouped bars) for P&L bridge
- [ ] **Heatmap Visualization**: Color-coded matrix for region × metric × year
- [ ] **Data Refresh Pipeline**: One-click re-ingestion when source file updates
- [ ] **Auto-Refresh**: Watch source file for changes and auto-re-run pipeline
- [ ] **WebSocket Updates**: Push data updates to connected browsers

---

## Change Log

### 2026-06-08 — v3.2 — Professionalization & Data Integrity

- Added `/api/data-freshness` with period coverage by year and version.
- Corrected FY2026 presentation: Actual is explicitly labeled YTD P01-P05.
- Reworked Scenario Comparison to combine Actual P01-P05 + T06 P06 + T07 P07-P12 instead of incorrectly treating them as competing full-year targets.
- Added semantic, keyboard-accessible dashboard tabs and clearer focus states.
- Added retry-safe lazy loading, same-year product comparison validation, and CSV formula-injection protection.
- Restricted static serving to `index.html` and `app.js`; database, workbook, source, and project files are no longer downloadable over HTTP.
- Removed local database paths and cache-key inventories from `/api/status`.
- Added `npm test` syntax and API/security smoke coverage via `smoke_test.js`.

### 2026-06-08 — v2.1 — Drill-Down Fix

- **CRITICAL FIX**: Drill-down only pre-computed 4 consecutive year pairs, but dashboard allows ANY year1/year2 combination (e.g., 2022→2026). Non-consecutive pairs returned 404 errors.
- Changed `precompute_data.py` to generate ALL 10 year pair combinations (was 4). Now 312 files (was 133).
- Added server-side fallback in `server.js`: if drill-down file not pre-computed, compute on-the-fly from cached view data (regional-pl, country-pl, mgroup-pl, customer-pl). This ensures drill-down ALWAYS works.
- All drill-down combinations now return 200 with 2-16ms response times.

### 2026-06-08 — v2.0 — Pre-Computed Static Backend

- **BREAKING**: Replaced Python subprocess query backend with pre-computed static JSON
- Created `precompute_data.py` to generate JSON files from SQLite
- Rewrote `server.js` to load all JSON into memory at startup (instant responses)
- Separated dashboard JavaScript into `app.js` for maintainability
- Added client-side data caching (regional + product data fetched once)
- Added lazy tab loading (data fetched only when tab is first visited)
- Added error handling with toast notifications
- Added input validation (year1 ≠ year2 check)
- Added loading state on drill-down button
- Added `safeFetch()` with timeout and error handling
- API response times improved from 1-5s to 2-35ms (100-1750x faster)
- Updated SKILL.md with new architecture documentation

### 2026-06-08 — v1.0 — Initial Build

- Built COM Excel extraction pipeline for Sheet1 (790K rows) and Sheet3 (pivot summary)
- Created SQLite database with 12 indexes and 6 analytical views
- Built Node.js API server with 9 endpoints using Python sqlite3 backend
- Built 4-tab interactive dashboard with Chart.js
- Documented entire system in SKILL.md
