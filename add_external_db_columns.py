#!/usr/bin/env python3
"""
为外部PostgreSQL数据库添加缺失的字段
"""
import os
import sys
from sqlalchemy import create_engine, text

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flowslide.core.simple_config import EXTERNAL_DATABASE_URL

def add_external_columns():
    """为外部数据库添加缺失的字段"""
    print("🔧 Adding missing columns to external PostgreSQL database...")

    if not EXTERNAL_DATABASE_URL:
        print("❌ No external database URL configured")
        return

    try:
        # 创建外部数据库引擎
        engine = create_engine(EXTERNAL_DATABASE_URL)

        with engine.connect() as conn:
            # 检查users表结构
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND table_schema = 'public'"))
            existing_columns = [row[0] for row in result.fetchall()]

            print(f"📊 Existing columns in external users table: {existing_columns}")

            # 添加updated_at字段（如果不存在）
            if 'updated_at' not in existing_columns:
                print("📝 Adding updated_at column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN updated_at DOUBLE PRECISION DEFAULT 0"))
                conn.commit()
                print("✅ Added updated_at column")
            else:
                print("✅ updated_at column already exists")

            # 添加sync_timestamp字段（如果不存在）
            if 'sync_timestamp' not in existing_columns:
                print("📝 Adding sync_timestamp column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN sync_timestamp DOUBLE PRECISION DEFAULT 0"))
                conn.commit()
                print("✅ Added sync_timestamp column")
            else:
                print("✅ sync_timestamp column already exists")

        engine.dispose()
        print("✅ External database schema updated successfully!")

    except Exception as e:
        print(f"❌ Failed to update external database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_external_columns()
