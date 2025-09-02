import sqlite3, time, json
from passlib.context import CryptContext
pwd = 'password'
ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
ph = ctx.hash(pwd)
DB='data/flowslide.db'
con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
cur=con.cursor()
cur.execute("SELECT id, username, password_hash, created_at, updated_at FROM users WHERE username='admin'")
row=cur.fetchone()
if row:
    print('FOUND', dict(row))
    # update password_hash to default and set created_at older
    cur.execute("UPDATE users SET password_hash=?, created_at=? WHERE id=?", (ph, time.time()-86400*365, row['id']))
    con.commit()
    print('UPDATED')
else:
    # insert a new admin with id set to a high number to avoid clashing with external id
    import random
    new_id = int(time.time()) % 1000000
    cur.execute('INSERT INTO users (id, username, password_hash, email, is_active, is_admin, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)', (new_id, 'admin', ph, 'admin@local', 1, 1, time.time()-86400*365, time.time()-86400*365))
    con.commit()
    print('INSERTED', new_id)
con.close()
