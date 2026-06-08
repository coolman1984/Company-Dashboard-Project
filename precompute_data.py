"""
Pre-compute all dashboard data as JSON files for instant API responses.
Run this once after database creation or data refresh.
"""
import sqlite3
import json
import os
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pl_detail.db")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_data")

os.makedirs(OUT_DIR, exist_ok=True)

def query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def save(name, data):
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, default=str)
    print(f"  OK {name}.json ({len(data) if isinstance(data, list) else 'object'})")

def main():
    start = time.time()
    print("Pre-computing dashboard data...")
    
    # 1. Summary
    row = query("SELECT COUNT(*) as total_rows FROM pl_detail")[0]
    years = [r['year'] for r in query("SELECT DISTINCT year FROM pl_detail ORDER BY year")]
    regions = [r['region_desc'] for r in query("SELECT DISTINCT region_desc FROM pl_detail WHERE region_desc IS NOT NULL ORDER BY region_desc")]
    mgroups = [r['m_group_desc'] for r in query("SELECT DISTINCT m_group_desc FROM pl_detail WHERE m_group_desc IS NOT NULL ORDER BY m_group_desc")]
    countries = [r['country_name'] for r in query("SELECT DISTINCT country_name FROM pl_detail WHERE country_name IS NOT NULL ORDER BY country_name")]
    customers = [r['customer_name'] for r in query("SELECT DISTINCT customer_name FROM pl_detail WHERE customer_name IS NOT NULL ORDER BY customer_name")]
    save("summary", {"totalRows": row['total_rows'], "years": years, "regions": regions, "mgroups": mgroups, "countries": countries, "customers": customers})
    
    # 2. Yearly PL
    save("yearly-pl", query("SELECT * FROM v_yearly_pl ORDER BY year"))
    
    # 3. Regional PL
    save("regional-pl", query("SELECT * FROM v_regional_pl ORDER BY year, region_desc"))
    
    # 4. Product group PL
    save("mgroup-pl", query("SELECT * FROM v_mgroup_pl ORDER BY year, m_group_desc"))
    
    # 5. Country PL
    save("country-pl", query("SELECT * FROM v_country_pl ORDER BY year, region_desc, country_name"))
    
    # 6. Customer PL (top 50 per year)
    save("customer-pl", query("SELECT * FROM v_customer_pl ORDER BY year, net_sales DESC LIMIT 250"))
    
    # 7. YoY variance
    save("yoy-variance", query("SELECT * FROM v_yoy_variance ORDER BY year"))
    
    # 8. Pre-compute drill-down for all dimension × metric × year combinations
    print("\nPre-computing drill-down data...")
    dimensions = ['region_desc', 'country_name', 'm_group_desc', 'customer_name', 'class']
    metrics = ['net_sales', 'cost_of_goods_sold', 'gross_margin', 'operating_expense', 'operating_profit', 'net_income']
    # All possible year pairs (not just consecutive)
    year_pairs = [(y1,y2) for y1 in [2022,2023,2024,2025,2026] for y2 in [2022,2023,2024,2025,2026] if y1 < y2]
    
    dd_count = 0
    for dim in dimensions:
        for metric in metrics:
            for y1, y2 in year_pairs:
                sql = f"""
                    SELECT 
                        {dim} as dimension,
                        SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END) as val_year1,
                        SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END) as val_year2,
                        SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END) - 
                            SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END) as change,
                        CASE WHEN SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END) != 0
                            THEN ROUND((SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END) - 
                                SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END)) / 
                                ABS(SUM(CASE WHEN year = ? AND version = 'Actual' THEN {metric} ELSE 0 END)) * 100, 2)
                            ELSE NULL END as pct_change
                    FROM pl_detail
                    WHERE year IN (?, ?) AND version = 'Actual'
                    GROUP BY {dim}
                    HAVING val_year1 != 0 OR val_year2 != 0
                    ORDER BY ABS(change) DESC
                    LIMIT 30
                """
                data = query(sql, [y1, y2, y2, y1, y1, y2, y1, y1, y1, y2])
                fname = f"drilldown_{dim}_{metric}_{y1}_{y2}"
                save(fname, data)
                dd_count += 1
    
    # 9. Pre-compute top product groups per year (for product analysis tab)
    print("\nPre-computing product top lists...")
    for year in years:
        data = query("""
            SELECT year, m_group_desc,
                SUM(net_sales) as net_sales,
                SUM(cost_of_goods_sold) as cogs,
                SUM(gross_margin) as gross_margin,
                SUM(operating_expense) as opex,
                SUM(operating_profit) as operating_profit,
                SUM(net_income) as net_income
            FROM pl_detail
            WHERE year = ? AND version = 'Actual'
            GROUP BY m_group_desc
            ORDER BY net_sales DESC
            LIMIT 30
        """, [year])
        save(f"top_products_{year}", data)
    
    elapsed = time.time() - start
    print(f"\nDone! Pre-computed {dd_count + 8 + len(years)} files in {elapsed:.1f}s")
    print(f"Output: {OUT_DIR}")

if __name__ == "__main__":
    main()
