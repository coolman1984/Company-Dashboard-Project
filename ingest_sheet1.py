"""
Ingest Sheet1 data (790K rows × 59 cols) from PL 2022~2026.xlsb into SQLite database.
Uses Excel COM to read data in chunks and bulk-insert into SQLite for maximum performance.

Strategy:
- Read 10,000 rows at a time via COM (bulk range read)
- Insert each chunk via executemany() inside a transaction
- Create indexes after all data is loaded (much faster than incremental indexing)
- Total estimated time: ~3-5 minutes for 790K rows
"""
import argparse
import os
import sys
import time
import sqlite3

# Shared, hardened COM helpers (lazy win32com import inside, so this file
# imports cleanly on any platform for --help / syntax checks).
from extractor import com_utils

# ===== CONFIGURATION =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XLSB_PATH = os.path.join(BASE_DIR, "PL 2022~2026.xlsb")
DB_PATH = os.path.join(BASE_DIR, "pl_detail.db")
CHUNK_SIZE = 10000  # Rows per COM read + DB insert
SHEET_NAME = "Sheet1"   # Preferred match by name...
SHEET_INDEX = 2         # ...falling back to position (Agent.md: Sheet1 == Sheets(2)).

# 0-based column indices that hold integers (year, valuation_class).
INT_COLUMN_INDICES = (5, 13)

# ASCII status marker — the Windows console can't always print Unicode (✓),
# which raises UnicodeEncodeError mid-run (Agent.md gotcha).
OK = "[OK]"

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

def create_database(db_path=DB_PATH, assume_yes=False):
    """Create SQLite database with the PL detail table.

    If `db_path` exists it is rebuilt from scratch. Pass assume_yes=True (the
    --yes flag) to skip the interactive confirmation for unattended runs.
    """
    if os.path.exists(db_path):
        print(f"WARNING: Database already exists at {db_path}")
        print("Re-running ingestion will DELETE the existing database and rebuild from scratch.")
        if not assume_yes:
            response = input("Continue? Type 'yes' to confirm: ")
            if response.lower() != 'yes':
                print("Aborted.")
                sys.exit(0)
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Build CREATE TABLE statement
    col_defs = ", ".join(f'"{name}" {dtype}' for name, dtype in COLUMNS)
    create_sql = f'CREATE TABLE pl_detail ({col_defs})'
    cursor.execute(create_sql)
    conn.commit()

    print(f"Created database: {db_path}")
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
        print(f"  {OK} {idx_name} on ({idx_col}) - {elapsed:.1f}s")

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

def _coerce_row(clean_cells):
    """Turn a cleaned cell list into an insert tuple, fixing integer columns."""
    row = []
    for c, val in enumerate(clean_cells):
        if c in INT_COLUMN_INDICES and isinstance(val, float) and val == int(val):
            row.append(int(val))
        else:
            row.append(val)
    return tuple(row)


def ingest_data(xlsb_path=XLSB_PATH, db_path=DB_PATH, sheet_name=SHEET_NAME,
                sheet_index=SHEET_INDEX, assume_yes=False):
    """Read the detail sheet via Excel COM in chunks and bulk-insert to SQLite.

    Returns the number of rows inserted. Indexes/views/verification only run
    after a clean, complete load — never on a partial or failed one.
    """
    # Fail fast before touching COM or deleting any existing database.
    if not os.path.exists(xlsb_path):
        print(f"ERROR: source workbook not found: {xlsb_path}", file=sys.stderr)
        return 0

    conn = create_database(db_path, assume_yes=assume_yes)
    cursor = conn.cursor()

    # Initialised up front so the post-load block below can never hit an
    # UnboundLocalError if the COM section raises before the loop starts.
    total_inserted = 0
    load_succeeded = False
    error_cells = 0

    col_names = ", ".join(f'"{name}"' for name, _ in COLUMNS)
    placeholders = ", ".join("?" for _ in COLUMNS)
    insert_sql = f'INSERT INTO pl_detail ({col_names}) VALUES ({placeholders})'

    try:
        with com_utils.excel_session() as excel:
            print("\nOpening workbook...")
            workbook = com_utils.open_workbook(excel, xlsb_path, read_only=True)
            try:
                sheet = com_utils.find_sheet(workbook, name=sheet_name, index=sheet_index)
                print(f"Sheet: {sheet.Name}")

                total_rows = int(sheet.UsedRange.Rows.Count)
                total_cols = int(sheet.UsedRange.Columns.Count)
                data_rows = max(0, total_rows - 1)   # row 1 is the header
                print(f"Total rows: {total_rows}, Total columns: {total_cols}")

                start_time = time.time()
                # chunk_bounds yields inclusive 1-based ranges over data rows.
                bounds = list(com_utils.chunk_bounds(data_rows, CHUNK_SIZE, start_row=2))
                for chunk_idx, (chunk_start, chunk_end) in enumerate(bounds, start=1):
                    block = sheet.Range(
                        sheet.Cells(chunk_start, 1),
                        sheet.Cells(chunk_end, total_cols),
                    ).Value

                    rows_to_insert = []
                    for com_row in com_utils.normalize_block(block):
                        clean_cells = []
                        for val in com_row:
                            clean_val, had_error = com_utils.clean_com_value(val)
                            clean_cells.append(clean_val)
                            if had_error:
                                error_cells += 1
                        rows_to_insert.append(_coerce_row(clean_cells))

                    cursor.executemany(insert_sql, rows_to_insert)
                    conn.commit()

                    total_inserted += len(rows_to_insert)
                    elapsed = time.time() - start_time
                    rate = total_inserted / elapsed if elapsed > 0 else 0
                    eta = (data_rows - total_inserted) / rate if rate > 0 else 0
                    print(f"  Chunk {chunk_idx}/{len(bounds)}: Inserted {total_inserted:,} rows "
                          f"({rate:,.0f} rows/sec, ETA: {eta:.0f}s)")

                total_time = time.time() - start_time
                rate = total_inserted / total_time if total_time > 0 else 0
                print(f"\n{OK} Ingestion complete: {total_inserted:,} rows in "
                      f"{total_time:.1f}s ({rate:,.0f} rows/sec)")
                if error_cells:
                    print(f"  Note: {error_cells:,} cell(s) held formula errors -> stored as null.")
                load_succeeded = True
            finally:
                try:
                    workbook.Close(SaveChanges=False)
                except Exception:  # noqa: BLE001
                    pass
    except Exception as exc:  # noqa: BLE001
        import traceback
        print(f"ERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
    finally:
        print("Excel COM cleanup complete.")

    # Only finalise a clean, complete load. A failed/partial run leaves an
    # incomplete database that should be rebuilt — we do not index/publish it.
    if load_succeeded and total_inserted > 0:
        create_indexes(conn)
        create_summary_views(conn)

        cursor.execute("SELECT COUNT(*) FROM pl_detail")
        count = cursor.fetchone()[0]
        print(f"\nVerification: {count:,} rows in pl_detail table")

        cursor.execute("SELECT * FROM v_yearly_pl")
        print("\n--- Yearly P&L Summary ---")
        for row in cursor.fetchall():
            print(f"  {row}")

        for dim in ['year', 'region_desc', 'version', 'class']:
            cursor.execute(f"SELECT DISTINCT {dim} FROM pl_detail ORDER BY {dim}")
            vals = [r[0] for r in cursor.fetchall()]
            print(f"\nDistinct {dim}: {vals}")

        conn.close()
        db_size = os.path.getsize(db_path) / (1024 * 1024)
        print(f"\nDatabase saved: {db_path}")
        print(f"Database size: {db_size:.1f} MB")
    else:
        conn.close()
        print("\nWARNING: load did not complete — database is incomplete and was "
              "NOT indexed. Fix the error above and re-run.", file=sys.stderr)

    return total_inserted


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ingest the PL detail sheet from an .xlsb via Excel COM "
                    "(Windows + Excel only)."
    )
    parser.add_argument("--xlsb", default=XLSB_PATH, help="Source .xlsb workbook.")
    parser.add_argument("--db", default=DB_PATH, help="Output SQLite database.")
    parser.add_argument("--sheet", default=SHEET_NAME,
                        help="Detail sheet name (falls back to position 2).")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the overwrite confirmation (for unattended runs).")
    args = parser.parse_args(argv)

    rows = ingest_data(xlsb_path=args.xlsb, db_path=args.db,
                       sheet_name=args.sheet, assume_yes=args.yes)
    return 0 if rows > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
