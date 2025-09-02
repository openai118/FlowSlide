import sqlite3, json
DB='data/flowslide.db'
con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
cur=con.cursor()
cur.execute("SELECT id, username, password_hash, email, is_active, is_admin, created_at, updated_at, last_login FROM users WHERE username='admin'")
row=cur.fetchone()
if row:
    print(json.dumps(dict(row), ensure_ascii=False))
else:
    print('null')
