"""List FlowSlide users from the configured PostgreSQL database (no password hashes)."""

import os
import sys

import psycopg2

url = os.environ.get("DATABASE_URL")
if not url:
    print("DATABASE_URL is required", file=sys.stderr)
    sys.exit(1)

conn = psycopg2.connect(url, connect_timeout=20, sslmode="require")
conn.autocommit = True
cur = conn.cursor()

cur.execute(
    """
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
      AND table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY 1, 2
    """
)
print("=== TABLES ===")
for schema, name in cur.fetchall():
    print(f"{schema}.{name}")

cur.execute(
    """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'users'
    ORDER BY ordinal_position
    """
)
print("\n=== USERS COLUMNS ===")
for col in cur.fetchall():
    print(col)

cur.execute(
    """
    SELECT id, username, email, is_active, is_admin,
           to_timestamp(created_at) AS created_at,
           CASE WHEN last_login IS NULL THEN NULL ELSE to_timestamp(last_login) END AS last_login,
           length(password_hash) AS hash_len,
           left(password_hash, 7) AS hash_prefix
    FROM users
    ORDER BY id
    """
)
rows = cur.fetchall()
print(f"\n=== USERS ({len(rows)}) ===")
print("id | username | email | active | admin | created | last_login | hash_len | prefix")
for row in rows:
    print(" | ".join(str(x) for x in row))

cur.close()
conn.close()
