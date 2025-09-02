import json, sqlite3
db = r"data/flowslide.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("SELECT id, local_id, external_id, attempted_username, reason, created_at, resolved FROM sync_conflicts ORDER BY created_at DESC LIMIT 10;")
rows = [dict(r) for r in cur.fetchall()]
print(json.dumps(rows, ensure_ascii=False))
