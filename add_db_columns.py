#!/usr/bin/env python3
"""
添加缺失的数据库字段到现有数据库
"""
import sqlite3
import os
from pathlib import Path

def add_missing_columns():
    """添加缺失的数据库字段"""
    print("🔧 Adding missing database columns...")

    # 本地数据库路径
    db_path = Path("./data/flowslide.db")

    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 检查users表是否有updated_at列
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'updated_at' not in column_names:
            print("📝 Adding updated_at column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at REAL DEFAULT 0")
            print("✅ Added updated_at column")
        else:
            print("✅ updated_at column already exists")

        # 检查其他可能缺失的列
        if 'sync_timestamp' not in column_names:
            print("📝 Adding sync_timestamp column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN sync_timestamp REAL DEFAULT 0")
            print("✅ Added sync_timestamp column")

        conn.commit()
        conn.close()

        print("✅ Database schema updated successfully!")

    except Exception as e:
        print(f"❌ Failed to update database: {e}")

if __name__ == "__main__":
    add_missing_columns()
