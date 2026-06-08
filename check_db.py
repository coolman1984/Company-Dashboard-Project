import sqlite3, os
db = r"D:\WORK\Software Development\GitHub\Company Dashboard\pl_detail.db"
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM pl_detail")
print(f"Rows: {c.fetchone()[0]:,}")
conn.close()
sz = os.path.getsize(db) / 1024 / 1024
print(f"Size: {sz:.1f} MB")
