
import sqlite3, json, sys
conn = sqlite3.connect(r"d:\\WORK\\Software Development\\GitHub\\Company Dashboard\\pl_detail.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("\n                    SELECT \n                        region_desc as dimension,\n                        SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END) as val_year1,\n                        SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END) as val_year2,\n                        SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END) - \n                            SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END) as change,\n                        CASE WHEN SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END) != 0\n                            THEN ROUND((SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END) - \n                                SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END)) / \n                                ABS(SUM(CASE WHEN year = ? AND version = 'Actual' THEN net_sales ELSE 0 END)) * 100, 2)\n                            ELSE NULL END as pct_change\n                    FROM pl_detail\n                    WHERE year IN (?, ?) AND version = 'Actual'\n                    GROUP BY region_desc\n                    HAVING val_year1 != 0 OR val_year2 != 0\n                    ORDER BY ABS(change) DESC\n                    LIMIT 30\n                ", [2023,2024,2024,2023,2023,2024,2023,2023,2023,2024])
rows = [dict(r) for r in c.fetchall()]
print(json.dumps(rows, default=str))
conn.close()
