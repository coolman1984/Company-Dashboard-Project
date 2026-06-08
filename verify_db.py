import sqlite3, os

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pl_detail.db")
conn = sqlite3.connect(db)
c = conn.cursor()

# Row count
c.execute("SELECT COUNT(*) FROM pl_detail")
print(f"Total rows: {c.fetchone()[0]:,}")

# Check if views exist
c.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
views = [r[0] for r in c.fetchall()]
print(f"Views: {views}")

# Check if indexes exist
c.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
indexes = [r[0] for r in c.fetchall()]
print(f"Indexes: {indexes}")

# Test yearly PL view
if 'v_yearly_pl' in views:
    print("\n--- v_yearly_pl ---")
    c.execute("SELECT * FROM v_yearly_pl")
    for row in c.fetchall():
        print(f"  {row}")

# Test regional PL view
if 'v_regional_pl' in views:
    print("\n--- v_regional_pl (first 10) ---")
    c.execute("SELECT * FROM v_regional_pl LIMIT 10")
    for row in c.fetchall():
        print(f"  {row}")

# Test mgroup PL view
if 'v_mgroup_pl' in views:
    print("\n--- v_mgroup_pl (first 10) ---")
    c.execute("SELECT * FROM v_mgroup_pl LIMIT 10")
    for row in c.fetchall():
        print(f"  {row}")

# Distinct values
for dim in ['year', 'region_desc', 'version', 'class']:
    c.execute(f"SELECT DISTINCT {dim} FROM pl_detail ORDER BY {dim}")
    vals = [r[0] for r in c.fetchall()]
    print(f"\nDistinct {dim}: {vals}")

conn.close()
sz = os.path.getsize(db) / 1024 / 1024
print(f"\nDatabase size: {sz:.1f} MB")
