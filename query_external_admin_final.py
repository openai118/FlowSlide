import json
from sqlalchemy import create_engine, text
from src.flowslide.core.simple_config import EXTERNAL_DATABASE_URL
url = EXTERNAL_DATABASE_URL
print('USING_URL', url)
engine = create_engine(url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT id, username, email, created_at, updated_at, last_login FROM users WHERE username = :u"), {"u":"admin"}).fetchall()
    rows = [dict(r._mapping) for r in res]
    print(json.dumps(rows, ensure_ascii=False))
