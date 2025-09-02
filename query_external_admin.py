from sqlalchemy import create_engine, text
from src.flowslide.core.simple_config import EXTERNAL_DATABASE_URL
import json, sys
url = EXTERNAL_DATABASE_URL
try:
    engine = create_engine(url, connect_args={})
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, username, email, created_at, updated_at, last_login FROM users WHERE username = :u"), {"u":"admin"}).fetchall()
        rows = [dict(r) for r in res]
        print(json.dumps(rows, ensure_ascii=False))
except Exception as e:
    print('ERROR:'+str(e))
    sys.exit(1)
