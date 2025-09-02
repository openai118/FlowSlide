import os, json, sys
from sqlalchemy import create_engine, text
url = os.getenv('DATABASE_URL')
if not url:
    print('ERROR: DATABASE_URL not set')
    sys.exit(1)
try:
    engine = create_engine(url)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, username, email, created_at, updated_at, last_login FROM users WHERE username = :u"), {"u":"admin"}).fetchall()
        rows = [dict(r) for r in res]
        print(json.dumps(rows, ensure_ascii=False))
except Exception as e:
    print('ERROR:'+str(e))
    sys.exit(0)
