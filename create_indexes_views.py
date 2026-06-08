"""Create indexes and views on the existing pl_detail database."""
import sqlite3
import time
import os

db = r"D:\WORK\Software Development\GitHub\Company Dashboard\pl_detail.db"
conn = sqlite3.connect(db)
cursor = conn.cursor()

# Check existing indexes
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
existing = [r[0] for r in cursor.fetchall()]
print(f"Existing indexes: {existing}")

# Create missing indexes
indexes = [
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
    if idx_name not in existing:
        start = time.time()
        cursor.execute(f'CREATE INDEX "{idx_name}" ON pl_detail ({idx_col})')
        elapsed = time.time() - start
        conn.commit()
        print(f"  OK {idx_name} on ({idx_col}) - {elapsed:.1f}s")
    else:
        print(f"  SKIP {idx_name} already exists")

# Create views
print("\nCreating views...")

cursor.execute("DROP VIEW IF EXISTS v_yearly_pl")
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
print("  OK v_yearly_pl")

cursor.execute("DROP VIEW IF EXISTS v_regional_pl")
cursor.execute("""
    CREATE VIEW v_regional_pl AS
    SELECT 
        year, region_desc,
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
print("  OK v_regional_pl")

cursor.execute("DROP VIEW IF EXISTS v_mgroup_pl")
cursor.execute("""
    CREATE VIEW v_mgroup_pl AS
    SELECT 
        year, m_group_desc,
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
print("  OK v_mgroup_pl")

cursor.execute("DROP VIEW IF EXISTS v_country_pl")
cursor.execute("""
    CREATE VIEW v_country_pl AS
    SELECT 
        year, region_desc, country_name,
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
print("  OK v_country_pl")

cursor.execute("DROP VIEW IF EXISTS v_customer_pl")
cursor.execute("""
    CREATE VIEW v_customer_pl AS
    SELECT 
        year, customer_name, region_desc,
        SUM(net_sales) as net_sales,
        SUM(cost_of_goods_sold) as cogs,
        SUM(gross_margin) as gross_margin,
        SUM(operating_profit) as operating_profit,
        SUM(net_income) as net_income
    FROM pl_detail
    WHERE version = 'Actual'
    GROUP BY year, customer_name, region_desc
    ORDER BY year, net_sales DESC
""")
print("  OK v_customer_pl")

cursor.execute("DROP VIEW IF EXISTS v_yoy_variance")
cursor.execute("""
    CREATE VIEW v_yoy_variance AS
    SELECT 
        curr.year,
        curr.net_sales, prev.net_sales as prev_net_sales,
        curr.net_sales - prev.net_sales as net_sales_change,
        CASE WHEN prev.net_sales != 0 
            THEN ROUND((curr.net_sales - prev.net_sales) / ABS(prev.net_sales) * 100, 2)
            ELSE NULL END as net_sales_pct,
        curr.gross_margin, prev.gross_margin as prev_gross_margin,
        curr.gross_margin - prev.gross_margin as gross_margin_change,
        curr.operating_profit, prev.operating_profit as prev_operating_profit,
        curr.operating_profit - prev.operating_profit as operating_profit_change,
        curr.net_income, prev.net_income as prev_net_income,
        curr.net_income - prev.net_income as net_income_change
    FROM v_yearly_pl curr
    LEFT JOIN v_yearly_pl prev ON curr.year = prev.year + 1
""")
print("  OK v_yoy_variance")

conn.commit()

# Verify
print("\n--- Verification ---")
cursor.execute("SELECT * FROM v_yearly_pl")
print("v_yearly_pl:")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT * FROM v_yoy_variance")
print("\nv_yoy_variance:")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT * FROM v_regional_pl LIMIT 5")
print("\nv_regional_pl (first 5):")
for row in cursor.fetchall():
    print(f"  {row}")

cursor.execute("SELECT * FROM v_mgroup_pl LIMIT 5")
print("\nv_mgroup_pl (first 5):")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
sz = os.path.getsize(db) / 1024 / 1024
print(f"\nDatabase size: {sz:.1f} MB")
print("Done!")
