import sqlite3, os
db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pl_detail.db")
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM pl_detail")
print(f"Rows: {c.fetchone()[0]:,}")
conn.close()
sz = os.path.getsize(db) / 1024 / 1024
print(f"Size: {sz:.1f} MB")
