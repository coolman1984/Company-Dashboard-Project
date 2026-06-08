"""
Ingest Sheet1 data (790K rows × 59 cols) from PL 2022~2026.xlsb into SQLite database.
Uses Excel COM to read data in chunks and bulk-insert into SQLite for maximum performance.

Strategy:
- Read 10,000 rows at a time via COM (bulk range read)
- Insert each chunk via executemany() inside a transaction
- Create indexes after all data is loaded (much faster than incremental indexing)
- Total estimated time: ~3-5 minutes for 790K rows
"""
import os
import sys
import time
import sqlite3
import pythoncom
import win32com.client

# ===== CONFIGURATION =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XLSB_PATH = os.path.join(BASE_DIR, "PL 2022~2026.xlsb")
DB_PATH = os.path.join(BASE_DIR, "pl_detail.db")
CHUNK_SIZE = 10000  # Rows per COM read + DB insert

# Column definitions: (column_name, sql_type)
COLUMNS = [
    ("class", "TEXT"),
    ("region_desc", "TEXT"),
    ("country_name", "TEXT"),
    ("customer_name", "TEXT"),
    ("m_group_desc", "TEXT"),
    ("year", "INTEGER"),
    ("class_code", "TEXT"),
    ("version", "TEXT"),
    ("product_number", "TEXT"),
    ("sender_ba", "TEXT"),
    ("customer_code", "TEXT"),
    ("country_code", "TEXT"),
    ("profit_center", "TEXT"),
    ("valuation_class", "REAL"),
    ("period", "REAL"),
    ("currency", "TEXT"),
    ("qty_gross", "REAL"),
    ("qty_return", "REAL"),
    ("qty_net", "REAL"),
    ("s_rrp", "REAL"),
    ("reference_price", "REAL"),
    ("dealer_discount", "REAL"),
    ("s_base_margin", "REAL"),
    ("s_contract_margin", "REAL"),
    ("s_additional_margin", "REAL"),
    ("s_special_margin", "REAL"),
    ("s_gross_sales", "REAL"),
    ("s_gross_sales_amt", "REAL"),
    ("s_other_sales", "REAL"),
    ("s_oth_sales_tax_inc", "REAL"),
    ("s_internal_sales_amt", "REAL"),
    ("s_return_amt", "REAL"),
    ("s_return_amt_alt", "REAL"),
    ("ref_sales", "REAL"),
    ("s_ifc", "REAL"),
    ("s_fob_sales_amt", "REAL"),
    ("sales_deduction", "REAL"),
    ("s_sales_allowance", "REAL"),
    ("s_rebate", "REAL"),
    ("s_cash_discount", "REAL"),
    ("s_price_protection", "REAL"),
    ("s_coop", "REAL"),
    ("s_sale_deduction_tax", "REAL"),
    ("net_sales", "REAL"),
    ("cost_of_goods_sold", "REAL"),
    ("material_cost", "REAL"),
    ("gross_margin", "REAL"),
    ("operating_expense", "REAL"),
    ("sales_expense", "REAL"),
    ("operating_profit", "REAL"),
    ("profit_before_tax", "REAL"),
    ("corporate_tax", "REAL"),
    ("corp_tax", "REAL"),
    ("net_income", "REAL"),
    ("sa_hq_sales_comm", "REAL"),
    ("sa_corp_promotion", "REAL"),
    ("royalty", "REAL"),
    ("sa_royalty_3rd_party", "REAL"),
    ("sa_royalty_hq", "REAL"),
]

def create_database():
    """Create SQLite database with the PL detail table."""
    if os.path.exists(DB_PATH):
        print(f"WARNING: Database already exists at {DB_PATH}")
        print(f"Re-running ingestion will DELETE the existing database and rebuild from scratch.")
        response = input("Continue? Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build CREATE TABLE statement
    col_defs = ", ".join(f'"{name}" {dtype}' for name, dtype in COLUMNS)
    create_sql = f'CREATE TABLE pl_detail ({col_defs})'
    cursor.execute(create_sql)
    conn.commit()

    print(f"Created database: {DB_PATH}")
    print(f"Table: pl_detail ({len(COLUMNS)} columns)")
    return conn

def create_indexes(conn):
    """Create indexes for fast analytical queries."""
    cursor = conn.cursor()

    indexes = [
        ("idx_year", "year"),
        ("idx_region", "region_desc"),
        ("idx_country", "country_name"),
        ("idx_customer", "customer_name"),
        ("idx_mgroup", "m_group_desc"),
        ("idx_class", "class"),
        ("idx_version", "version"),
        ("idx_period", "period"),
        ("idx_profit_center", "profit_center"),
        ("idx_product", "product_number"),
        ("idx_year_region", "year, region_desc"),
        ("idx_year_mgroup", "year, m_group_desc"),
        ("idx_year_customer", "year, customer_name"),
    ]

    print("\nCreating indexes...")
    for idx_name, idx_col in indexes:
        start = time.time()
        cursor.execute(f'CREATE INDEX "{idx_name}" ON pl_detail ({idx_col})')
        elapsed = time.time() - start
        print(f"  ✓ {idx_name} on ({idx_col}) — {elapsed:.1f}s")

    conn.commit()
    print("All indexes created.")

def create_summary_views(conn):
    """Create pre-computed summary views for the dashboard."""
    cursor = conn.cursor()

    # Yearly P&L summary (matches Sheet3 pivot)
    cursor.execute("""
        CREATE VIEW v_yearly_pl AS
        SELECT
            year,
            SUM(net_sales) as net_sales,
            SUM(cost_of_goods_sold) as cogs,
            SUM(gross_margin) as gross_margin,
            SUM(operating_expense) as opex,
            SUM(operating_profit) as operating_profit,
            SUM(net_income) as net_income,
            SUM(s_gross_sales) as gross_sales,
            SUM(s_return_amt) as returns,
            SUM(sales_deduction) as sales_deduction,
            SUM(material_cost) as material_cost,
            SUM(sales_expense) as sales_expense,
            SUM(profit_before_tax) as profit_before_tax,
            SUM(corporate_tax) as corporate_tax,
            SUM(royalty) as royalty
        FROM pl_detail
        WHERE version = 'Actual'
        GROUP BY year
        ORDER BY year
    """)

    # Regional P&L by year
    cursor.execute("""
        CREATE VIEW v_regional_pl AS
        SELECT
            year,
            region_desc,
            SUM(net_sales) as net_sales,
            SUM(cost_of_goods_sold) as cogs,
            SUM(gross_margin) as gross_margin,
            SUM(operating_expense) as opex,
            SUM(operating_profit) as operating_profit,
            SUM(net_income) as net_income
        FROM pl_detail
        WHERE version = 'Actual'
        GROUP BY year, region_desc
        ORDER BY year, region_desc
    """)

    # Product group P&L by year
    cursor.execute("""
        CREATE VIEW v_mgroup_pl AS
        SELECT
            year,
            m_group_desc,
            SUM(net_sales) as net_sales,
            SUM(cost_of_goods_sold) as cogs,
            SUM(gross_margin) as gross_margin,
            SUM(operating_expense) as opex,
            SUM(operating_profit) as operating_profit,
            SUM(net_income) as net_income
        FROM pl_detail
        WHERE version = 'Actual'
        GROUP BY year, m_group_desc
        ORDER BY year, m_group_desc
    """)

    # Country P&L by year
    cursor.execute("""
        CREATE VIEW v_country_pl AS
        SELECT
            year,
            region_desc,
            country_name,
            SUM(net_sales) as net_sales,
            SUM(cost_of_goods_sold) as cogs,
            SUM(gross_margin) as gross_margin,
            SUM(operating_expense) as opex,
            SUM(operating_profit) as operating_profit,
            SUM(net_income) as net_income
        FROM pl_detail
        WHERE version = 'Actual'
        GROUP BY year, region_desc, country_name
        ORDER BY year, region_desc, country_name
    """)

    # Customer P&L by year (top customers)
    cursor.execute("""
        CREATE VIEW v_customer_pl AS
        SELECT
            year,
            customer_name,
            region_desc,
            SUM(net_sales) as net_sales,
            SUM(cost_of_goods_sold) as cogs,
            SUM(gross_margin) as gross_margin,
            SUM(operating_expense) as opex,
            SUM(operating_profit) as operating_profit,
            SUM(net_income) as net_income
        FROM pl_detail
        WHERE version = 'Actual'
        GROUP BY year, customer_name, region_desc
        ORDER BY year, net_sales DESC
    """)

    # YoY variance view
    cursor.execute("""
        CREATE VIEW v_yoy_variance AS
        SELECT
            curr.year,
            curr.net_sales as net_sales,
            prev.net_sales as prev_net_sales,
            curr.net_sales - prev.net_sales as net_sales_change,
            CASE WHEN prev.net_sales != 0
                THEN ROUND((curr.net_sales - prev.net_sales) / ABS(prev.net_sales) * 100, 2)
                ELSE NULL END as net_sales_pct_change,
            curr.gross_margin as gross_margin,
            prev.gross_margin as prev_gross_margin,
            curr.gross_margin - prev.gross_margin as gross_margin_change,
            CASE WHEN prev.gross_margin != 0
                THEN ROUND((curr.gross_margin - prev.gross_margin) / ABS(prev.gross_margin) * 100, 2)
                ELSE NULL END as gross_margin_pct_change,
            curr.operating_profit as operating_profit,
            prev.operating_profit as prev_operating_profit,
            curr.operating_profit - prev.operating_profit as operating_profit_change,
            curr.net_income as net_income,
            prev.net_income as prev_net_income,
            curr.net_income - prev.net_income as net_income_change
        FROM v_yearly_pl curr
        LEFT JOIN v_yearly_pl prev ON curr.year = prev.year + 1
    """)

    conn.commit()
    print("Created summary views: v_yearly_pl, v_regional_pl, v_mgroup_pl, v_country_pl, v_customer_pl, v_yoy_variance")

def ingest_data():
    """Main ingestion: read from Excel via COM in chunks, insert into SQLite."""
    conn = create_database()
    cursor = conn.cursor()

    pythoncom.CoInitialize()
    excel = None

    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        print("\nOpening workbook...")
        workbook = excel.Workbooks.Open(XLSB_PATH, ReadOnly=True)
        sheet = workbook.Sheets(2)  # Sheet1
        print(f"Sheet: {sheet.Name}")

        total_rows = sheet.UsedRange.Rows.Count
        total_cols = sheet.UsedRange.Columns.Count
        print(f"Total rows: {total_rows}, Total columns: {total_cols}")

        # Prepare insert statement
        col_names = ", ".join(f'"{name}"' for name, _ in COLUMNS)
        placeholders = ", ".join("?" for _ in COLUMNS)
        insert_sql = f'INSERT INTO pl_detail ({col_names}) VALUES ({placeholders})'

        # Read and insert in chunks
        total_inserted = 0
        start_time = time.time()

        # Start from row 2 (row 1 is headers)
        data_start_row = 2
        num_chunks = (total_rows - 1 + CHUNK_SIZE - 1) // CHUNK_SIZE

        for chunk_idx in range(num_chunks):
            chunk_start = data_start_row + (chunk_idx * CHUNK_SIZE)
            chunk_end = min(chunk_start + CHUNK_SIZE - 1, total_rows)

            # Bulk read this chunk via COM
            chunk_range = sheet.Range(
                sheet.Cells(chunk_start, 1),
                sheet.Cells(chunk_end, total_cols)
            )
            chunk_data = chunk_range.Value

            # Convert to list of tuples for executemany
            rows_to_insert = []
            for r in range(len(chunk_data)):
                row = []
                for c in range(len(chunk_data[r])):
                    val = chunk_data[r][c]
                    if val is None:
                        row.append(None)
                    elif isinstance(val, float) and val == int(val) and c in (5, 13):  # Year, Valuation Class
                        row.append(int(val))
                    else:
                        row.append(val)
                rows_to_insert.append(tuple(row))

            # Bulk insert
            cursor.executemany(insert_sql, rows_to_insert)
            conn.commit()

            total_inserted += len(rows_to_insert)
            elapsed = time.time() - start_time
            rate = total_inserted / elapsed if elapsed > 0 else 0
            eta = (total_rows - 1 - total_inserted) / rate if rate > 0 else 0

            print(f"  Chunk {chunk_idx+1}/{num_chunks}: Inserted {total_inserted:,} rows "
                  f"({rate:,.0f} rows/sec, ETA: {eta:.0f}s)")

        total_time = time.time() - start_time
        print(f"\n✓ Ingestion complete: {total_inserted:,} rows in {total_time:.1f}s "
              f"({total_inserted/total_time:,.0f} rows/sec)")

        workbook.Close(SaveChanges=False)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if excel:
            try:
                excel.Quit()
            except:
                pass
        pythoncom.CoUninitialize()
        print("Excel COM cleanup complete.")

    # Create indexes and views
    if total_inserted > 0:
        create_indexes(conn)
        create_summary_views(conn)

        # Verify data
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pl_detail")
        count = cursor.fetchone()[0]
        print(f"\nVerification: {count:,} rows in pl_detail table")

        cursor.execute("SELECT * FROM v_yearly_pl")
        print("\n--- Yearly P&L Summary ---")
        for row in cursor.fetchall():
            print(f"  {row}")

        # Show distinct values for key dimensions
        for dim in ['year', 'region_desc', 'version', 'class']:
            cursor.execute(f"SELECT DISTINCT {dim} FROM pl_detail ORDER BY {dim}")
            vals = [r[0] for r in cursor.fetchall()]
            print(f"\nDistinct {dim}: {vals}")

    conn.close()
    print(f"\nDatabase saved: {DB_PATH}")
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"Database size: {db_size:.1f} MB")

if __name__ == "__main__":
    ingest_data()
