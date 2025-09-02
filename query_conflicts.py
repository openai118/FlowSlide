import json, sqlite3
DB='data/flowslide.db'
con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
cur=con.cursor()
cur.execute("SELECT id, local_id, external_id, attempted_username, reason, payload, created_at, resolved FROM sync_conflicts ORDER BY created_at DESC LIMIT 20;")
rows=[dict(r) for r in cur.fetchall()]
print(json.dumps(rows, ensure_ascii=False))
