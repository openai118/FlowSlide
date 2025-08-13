#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================
LandPPT 数据库压力测试工�?
==============================================
模拟真实应用场景的并发读写测�?
"""

import os
import sys
import json
import time
import threading
import concurrent.futures
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:
    print("�?请安�? pip install psycopg2-binary")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("�?请安�? pip install requests")
    sys.exit(1)


@dataclass
class TestResult:
    """测试结果数据�?""
    operation: str
    success: bool
    duration: float
    error: str = ""
    thread_id: int = 0


class DatabaseStressTester:
    """数据库压力测试器"""
    
    def __init__(self, password: str):
        self.password = password
        self.results: List[TestResult] = []
        self.lock = threading.Lock()
        
        # 连接池配�?
        self.pool_config = {
            'host': 'your-supabase-host',
            'port': 5432,
            'database': 'postgres',
            'user': 'your_db_user',
            'password': 'your_secure_password',
            'sslmode': 'require'
        }
        
        # 存储配置
        self.storage_config = {
            'url': 'https://your-project.supabase.co',
            'service_key': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZpdXpldGF6cGVyZWJ1cXdtcm5hIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NDk1MjY2OCwiZXhwIjoyMDcwNTI4NjY4fQ.8vdb7DH860INPx5ZhDd9JTdsfJtDAhOizQNZgEqONNE',
            'bucket': 'landppt-files'
        }
        
        self.connection_pool = None
        
    def setup_connection_pool(self, min_connections: int = 5, max_connections: int = 20):
        """设置连接�?""
        try:
            self.connection_pool = ThreadedConnectionPool(
                min_connections,
                max_connections,
                **self.pool_config
            )
            print(f"�?连接池已创建 ({min_connections}-{max_connections} 连接)")
            return True
        except Exception as e:
            print(f"�?连接池创建失�? {e}")
            return False
            
    def cleanup_connection_pool(self):
        """清理连接�?""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("�?连接池已清理")
            
    def add_result(self, result: TestResult):
        """线程安全地添加测试结�?""
        with self.lock:
            self.results.append(result)
            
    def simulate_read_operations(self, thread_id: int, num_operations: int = 50):
        """模拟读取操作"""
        if not self.connection_pool:
            return
            
        conn = None
        try:
            conn = self.connection_pool.getconn()
            
            for i in range(num_operations):
                start_time = time.time()
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        # 模拟不同类型的查�?
                        queries = [
                            "SELECT COUNT(*) FROM deployment_verification;",
                            "SELECT * FROM deployment_verification ORDER BY created_at DESC LIMIT 5;",
                            "SELECT test_connection();",
                            "SELECT current_user, NOW();"
                        ]
                        
                        query = queries[i % len(queries)]
                        cur.execute(query)
                        result = cur.fetchall()
                        
                    duration = time.time() - start_time
                    self.add_result(TestResult(
                        operation=f"READ_{query[:20]}...",
                        success=True,
                        duration=duration,
                        thread_id=thread_id
                    ))
                    
                except Exception as e:
                    duration = time.time() - start_time
                    self.add_result(TestResult(
                        operation="READ_ERROR",
                        success=False,
                        duration=duration,
                        error=str(e),
                        thread_id=thread_id
                    ))
                    
                # 模拟真实应用的间�?
                time.sleep(0.1)
                
        finally:
            if conn and self.connection_pool:
                self.connection_pool.putconn(conn)
                
    def simulate_write_operations(self, thread_id: int, num_operations: int = 20):
        """模拟写入操作"""
        if not self.connection_pool:
            return
            
        conn = None
        try:
            conn = self.connection_pool.getconn()
            
            for i in range(num_operations):
                start_time = time.time()
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        # 插入测试数据
                        message = f"压力测试 Thread-{thread_id} Op-{i} {datetime.now().isoformat()}"
                        cur.execute("""
                            INSERT INTO deployment_verification (message) 
                            VALUES (%s) RETURNING id;
                        """, (message,))
                        insert_result = cur.fetchone()
                        
                        # 立即删除（避免污染数据）
                        cur.execute("DELETE FROM deployment_verification WHERE id = %s;", (insert_result['id'],))
                        
                    conn.commit()
                    duration = time.time() - start_time
                    self.add_result(TestResult(
                        operation="WRITE_INSERT_DELETE",
                        success=True,
                        duration=duration,
                        thread_id=thread_id
                    ))
                    
                except Exception as e:
                    conn.rollback()
                    duration = time.time() - start_time
                    self.add_result(TestResult(
                        operation="WRITE_ERROR",
                        success=False,
                        duration=duration,
                        error=str(e),
                        thread_id=thread_id
                    ))
                    
                # 写入操作间隔稍长
                time.sleep(0.2)
                
        finally:
            if conn and self.connection_pool:
                self.connection_pool.putconn(conn)
                
    def simulate_storage_operations(self, thread_id: int, num_operations: int = 10):
        """模拟存储操作"""
        headers = {
            'Authorization': f'Bearer {self.storage_config["service_key"]}',
        }
        
        for i in range(num_operations):
            start_time = time.time()
            try:
                # 创建测试文件
                test_content = f"压力测试文件 Thread-{thread_id} Op-{i}\n时间: {datetime.now().isoformat()}"
                filename = f"stress_test_t{thread_id}_op{i}_{int(time.time())}.txt"
                
                # 上传文件
                upload_url = f"{self.storage_config['url']}/storage/v1/object/{self.storage_config['bucket']}/{filename}"
                upload_response = requests.post(
                    upload_url,
                    headers=headers,
                    files={'file': (filename, test_content, 'text/plain')},
                    timeout=30
                )
                
                if upload_response.status_code in [200, 201]:
                    # 下载验证
                    download_response = requests.get(upload_url, headers=headers, timeout=30)
                    
                    if download_response.status_code == 200:
                        # 删除文件
                        requests.delete(upload_url, headers=headers, timeout=30)
                        
                        duration = time.time() - start_time
                        self.add_result(TestResult(
                            operation="STORAGE_UPLOAD_DOWNLOAD_DELETE",
                            success=True,
                            duration=duration,
                            thread_id=thread_id
                        ))
                    else:
                        raise Exception(f"下载失败: {download_response.status_code}")
                else:
                    raise Exception(f"上传失败: {upload_response.status_code}")
                    
            except Exception as e:
                duration = time.time() - start_time
                self.add_result(TestResult(
                    operation="STORAGE_ERROR",
                    success=False,
                    duration=duration,
                    error=str(e),
                    thread_id=thread_id
                ))
                
            time.sleep(0.5)
            
    def run_concurrent_test(self, num_threads: int = 10, test_duration: int = 60):
        """运行并发压力测试"""
        print(f"🚀 开始并发压力测�?..")
        print(f"   线程�? {num_threads}")
        print(f"   测试时长: {test_duration} �?)
        print("-" * 50)
        
        if not self.setup_connection_pool(min_connections=5, max_connections=num_threads + 5):
            return False
            
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            
            # 启动不同类型的工作线�?
            for i in range(num_threads):
                if i % 3 == 0:
                    # 读取密集型线�?
                    future = executor.submit(self.simulate_read_operations, i, 100)
                elif i % 3 == 1:
                    # 写入线程
                    future = executor.submit(self.simulate_write_operations, i, 30)
                else:
                    # 存储操作线程
                    future = executor.submit(self.simulate_storage_operations, i, 15)
                    
                futures.append(future)
                
            # 等待所有线程完成或超时
            for future in concurrent.futures.as_completed(futures, timeout=test_duration + 30):
                try:
                    future.result()
                except Exception as e:
                    print(f"⚠️ 线程异常: {e}")
                    
        elapsed_time = time.time() - start_time
        self.cleanup_connection_pool()
        
        print(f"�?压力测试完成，耗时: {elapsed_time:.2f} �?)
        return True
        
    def analyze_results(self) -> Dict[str, Any]:
        """分析测试结果"""
        if not self.results:
            return {'error': '没有测试结果'}
            
        # 按操作类型分�?
        operations = {}
        for result in self.results:
            op_type = result.operation.split('_')[0]  # READ, WRITE, STORAGE
            if op_type not in operations:
                operations[op_type] = {
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'durations': [],
                    'errors': []
                }
                
            operations[op_type]['total'] += 1
            if result.success:
                operations[op_type]['success'] += 1
                operations[op_type]['durations'].append(result.duration)
            else:
                operations[op_type]['failed'] += 1
                operations[op_type]['errors'].append(result.error)
                
        # 计算统计信息
        analysis = {
            'summary': {
                'total_operations': len(self.results),
                'total_success': len([r for r in self.results if r.success]),
                'total_failed': len([r for r in self.results if not r.success]),
                'success_rate': f"{len([r for r in self.results if r.success]) / len(self.results) * 100:.1f}%"
            },
            'by_operation': {}
        }
        
        for op_type, stats in operations.items():
            if stats['durations']:
                durations = stats['durations']
                analysis['by_operation'][op_type] = {
                    'total': stats['total'],
                    'success': stats['success'],
                    'failed': stats['failed'],
                    'success_rate': f"{stats['success'] / stats['total'] * 100:.1f}%",
                    'avg_duration': f"{sum(durations) / len(durations):.3f}s",
                    'min_duration': f"{min(durations):.3f}s",
                    'max_duration': f"{max(durations):.3f}s",
                    'errors': stats['errors'][:5]  # 只显示前5个错�?
                }
                
        return analysis
        
    def print_analysis(self):
        """打印分析结果"""
        analysis = self.analyze_results()
        
        print("\n" + "=" * 50)
        print("📊 压力测试结果分析")
        print("=" * 50)
        
        # 总体统计
        summary = analysis['summary']
        print(f"总操作数: {summary['total_operations']}")
        print(f"成功操作: {summary['total_success']}")
        print(f"失败操作: {summary['total_failed']}")
        print(f"成功�? {summary['success_rate']}")
        
        # 按操作类型分�?
        print("\n按操作类型分�?")
        print("-" * 30)
        for op_type, stats in analysis['by_operation'].items():
            print(f"\n{op_type} 操作:")
            print(f"  总数: {stats['total']}")
            print(f"  成功�? {stats['success_rate']}")
            print(f"  平均耗时: {stats['avg_duration']}")
            print(f"  最短耗时: {stats['min_duration']}")
            print(f"  最长耗时: {stats['max_duration']}")
            
            if stats['errors']:
                print(f"  主要错误: {stats['errors'][0] if stats['errors'] else 'None'}")
                
        # 性能评级
        total_success_rate = float(summary['success_rate'].rstrip('%'))
        if total_success_rate >= 95:
            grade = "优秀 🌟"
        elif total_success_rate >= 90:
            grade = "良好 👍"
        elif total_success_rate >= 80:
            grade = "一�?⚠️"
        else:
            grade = "需要优�?�?
            
        print(f"\n性能评级: {grade}")
        print("=" * 50)


def main():
    """主函�?""
    print("🔥 LandPPT 数据库压力测试工�?)
    print("=" * 50)
    
    # 获取配置
    password = input("请输入数据库 postgres 用户密码: ").strip()
    if not password:
        print("�?密码不能为空")
        return 1
        
    try:
        num_threads = int(input("并发线程�?(默认10): ").strip() or "10")
        test_duration = int(input("测试时长/�?(默认60): ").strip() or "60")
    except ValueError:
        print("�?请输入有效数�?)
        return 1
        
    # 运行测试
    tester = DatabaseStressTester(password)
    
    try:
        if tester.run_concurrent_test(num_threads, test_duration):
            tester.print_analysis()
            
            # 保存详细结果
            timestamp = int(time.time())
            results_file = f"stress_test_results_{timestamp}.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'config': {
                        'threads': num_threads,
                        'duration': test_duration,
                        'timestamp': datetime.now().isoformat()
                    },
                    'analysis': tester.analyze_results(),
                    'raw_results': [
                        {
                            'operation': r.operation,
                            'success': r.success,
                            'duration': r.duration,
                            'error': r.error,
                            'thread_id': r.thread_id
                        } for r in tester.results
                    ]
                }, f, ensure_ascii=False, indent=2)
                
            print(f"\n📄 详细结果已保存到: {results_file}")
            return 0
        else:
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中�?)
        tester.cleanup_connection_pool()
        return 130
    except Exception as e:
        print(f"\n�?测试异常: {e}")
        tester.cleanup_connection_pool()
        return 1


if __name__ == "__main__":
    sys.exit(main())
