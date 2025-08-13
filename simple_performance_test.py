#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================
LandPPT 简单性能验证工具
==============================================
快速验证数据库性能指标
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("�?请安�? pip install psycopg2-binary")
    exit(1)

def performance_test():
    """简单性能测试"""
    print("�?LandPPT 性能验证")
    print("=" * 40)
    
    config = {
        'host': 'your-supabase-host',
        'port': 5432,
        'database': 'postgres',
        'user': 'your_db_user',
        'password': 'your_secure_password',
        'sslmode': 'require'
    }
    
    results = []
    
    def single_operation(thread_id):
        """单个操作测试"""
        try:
            start_time = time.time()
            conn = psycopg2.connect(**config)
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 读取操作
                cur.execute("SELECT COUNT(*) as count FROM deployment_verification;")
                count = cur.fetchone()['count']
                
                # 写入操作
                test_msg = f"性能测试 T{thread_id} {datetime.now().strftime('%H:%M:%S.%f')}"
                cur.execute("INSERT INTO deployment_verification (message) VALUES (%s) RETURNING id;", (test_msg,))
                insert_id = cur.fetchone()['id']
                
                # 清理
                cur.execute("DELETE FROM deployment_verification WHERE id = %s;", (insert_id,))
                
            conn.commit()
            conn.close()
            
            duration = time.time() - start_time
            results.append(duration)
            print(f"   线程 {thread_id}: {duration:.3f}�?)
            return True
            
        except Exception as e:
            print(f"   线程 {thread_id} 失败: {e}")
            return False
    
    # 串行测试
    print("\n🔍 串行性能测试�?次操作）:")
    serial_times = []
    for i in range(5):
        start = time.time()
        single_operation(f"S{i}")
        serial_times.append(time.time() - start)
    
    # 并发测试
    print("\n🔍 并发性能测试�?个线程）:")
    results.clear()
    concurrent_start = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(single_operation, f"C{i}") for i in range(5)]
        success_count = sum(1 for future in futures if future.result())
    
    concurrent_duration = time.time() - concurrent_start
    
    # 结果分析
    print("\n" + "=" * 40)
    print("📊 性能分析结果:")
    print(f"   串行平均时间: {sum(serial_times)/len(serial_times):.3f}�?)
    
    if results:
        print(f"   并发平均时间: {sum(results)/len(results):.3f}�?)
        print(f"   并发总时�? {concurrent_duration:.3f}�?)
        print(f"   并发成功�? {success_count}/5 ({success_count/5*100:.0f}%)")
        
        # 性能评级
        avg_response = sum(results) / len(results)
        if avg_response < 0.5:
            grade = "优秀 🌟"
        elif avg_response < 1.0:
            grade = "良好 👍"
        elif avg_response < 2.0:
            grade = "一�?⚠️"
        else:
            grade = "需优化 �?
            
        print(f"   性能评级: {grade}")
    
    print("=" * 40)
    print("�?性能验证完成")

if __name__ == "__main__":
    try:
        performance_test()
    except Exception as e:
        print(f"�?性能测试失败: {e}")
