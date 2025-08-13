#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================
LandPPT 快速数据库连接检查工�?
==============================================
快速验证数据库基本功能
"""

import sys
import time
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("�?请安�? pip install psycopg2-binary")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("�?请安�? pip install requests")
    sys.exit(1)


def quick_database_check():
    """快速数据库检�?""
    print("🔍 LandPPT 快速数据库检�?)
    print("-" * 40)
    
    # 应用用户连接配置
    app_config = {
        'host': 'your-supabase-host',
        'port': 5432,
        'database': 'postgres',
        'user': 'your_db_user',
        'password': 'your_secure_password',
        'sslmode': 'require'
    }
    
    try:
        print("👤 测试应用用户连接...")
        conn = psycopg2.connect(**app_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 检查权�?
            cur.execute("SELECT current_user, current_setting('search_path') as search_path;")
            user_info = cur.fetchone()
            
            # 读取测试
            cur.execute("SELECT COUNT(*) as count FROM deployment_verification;")
            count_result = cur.fetchone()
            
            # 写入测试
            test_msg = f"快速检�?{datetime.now().strftime('%H:%M:%S')}"
            cur.execute("INSERT INTO deployment_verification (message) VALUES (%s) RETURNING id;", (test_msg,))
            insert_result = cur.fetchone()
            
            # 函数测试
            cur.execute("SELECT test_connection() as result;")
            func_result = cur.fetchone()
            
            # 清理
            cur.execute("DELETE FROM deployment_verification WHERE id = %s;", (insert_result['id'],))
            
        conn.commit()
        conn.close()
        
        print(f"�?应用用户正常: {user_info['current_user']}")
        print(f"�?搜索路径: {user_info['search_path']}")
        print(f"�?读写权限正常: 现有 {count_result['count']} 条记�?)
        print(f"�?函数调用正常: {func_result['result'][:50]}...")
        
    except Exception as e:
        print(f"�?应用用户连接/权限问题: {e}")
        return False
        
    # 存储 API 快速测�?
    try:
        print("📁 测试存储 API...")
        headers = {
            'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZpdXpldGF6cGVyZWJ1cXdtcm5hIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NDk1MjY2OCwiZXhwIjoyMDcwNTI4NjY4fQ.8vdb7DH860INPx5ZhDd9JTdsfJtDAhOizQNZgEqONNE',
            'Content-Type': 'application/json'
        }
        
        bucket_url = "https://your-project.supabase.co/storage/v1/bucket"
        response = requests.get(bucket_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            buckets = response.json()
            landppt_bucket = next((b for b in buckets if b['id'] == 'landppt-files'), None)
            if landppt_bucket:
                print(f"�?存储桶正�? {landppt_bucket['name']} (public: {landppt_bucket['public']})")
            else:
                print("�?未找�?landppt-files 存储�?)
                return False
        else:
            print(f"�?存储 API 访问失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"�?存储测试失败: {e}")
        return False
        
    print("-" * 40)
    print("🎉 所有检查通过！数据库状态正�?)
    return True


if __name__ == "__main__":
    if quick_database_check():
        sys.exit(0)
    else:
        sys.exit(1)
