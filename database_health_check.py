#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================
FlowSlide PostgreSQL 数据库健康检查工具
==============================================
全面检测数据库连接、权限、存储等功能
支持 PostgreSQL 及其衍生产品（如 Supabase）
"""

import os
import sys
import json
import time
import hashlib
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌错误: 请安装psycopg2-binary")
    print("运行: pip install psycopg2-binary")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌错误: 请安装requests")
    print("运行: pip install requests")
    sys.exit(1)


class PostgreSQLHealthChecker:
    """PostgreSQL 数据库健康检查器"""
    
    def __init__(self):
        """初始化检查器，从环境变量读取配置"""
        # 优先使用 DATABASE_URL，如果不存在则使用分离的环境变量
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # 解析 DATABASE_URL
            self.db_config = self._parse_database_url(database_url)
        else:
            # 使用分离的环境变量
            self.db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', ''),
                'sslmode': 'require'
            }
        
        # API 配置（可选，用于 REST API 测试）
        self.api_url = os.getenv('API_URL', '')
        self.api_anon_key = os.getenv('API_ANON_KEY', '')
        self.api_service_key = os.getenv('API_SERVICE_KEY', '')
        
        # 存储配置（可选）
        self.storage_bucket = os.getenv('STORAGE_BUCKET', '')
        self.storage_provider = os.getenv('STORAGE_PROVIDER', 'unknown')
        
        # postgres 超级用户配置（仅在需要时使用）
        self.admin_config = {
            'host': self.db_config['host'],
            'port': self.db_config['port'],
            'database': self.db_config['database'],
            'user': 'postgres',
            'password': os.getenv('POSTGRES_PASSWORD', ''),
            'sslmode': 'require'
        }
        
        # 检查结果存储
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'summary': {'total': 0, 'passed': 0, 'failed': 0, 'warnings': 0}
        }
    
    def _parse_database_url(self, url: str) -> Dict[str, Any]:
        """解析 DATABASE_URL"""
        try:
            parsed = urllib.parse.urlparse(url)
            
            # 解析查询参数
            query_params = urllib.parse.parse_qs(parsed.query)
            
            config = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path.lstrip('/'),
                'user': parsed.username,
                'password': parsed.password,
                'sslmode': 'require'
            }
            
            # 处理特殊的 options 参数
            if 'options' in query_params:
                config['options'] = query_params['options'][0]
            
            return config
        except Exception as e:
            print(f"❌ 解析 DATABASE_URL 失败: {e}")
            sys.exit(1)
    
    def add_result(self, check_name: str, passed: bool, message: str, 
                   details: Optional[Dict] = None, warning: bool = False):
        """添加检查结果"""
        self.results['checks'][check_name] = {
            'passed': passed,
            'warning': warning,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        
        self.results['summary']['total'] += 1
        if warning:
            self.results['summary']['warnings'] += 1
        elif passed:
            self.results['summary']['passed'] += 1
        else:
            self.results['summary']['failed'] += 1
    
    def _resolve_host_ipv6(self, hostname: str) -> str:
        """尝试解析主机名为IPv6地址，如果失败则返回原主机名"""
        try:
            import socket
            # 尝试IPv4
            try:
                info = socket.getaddrinfo(hostname, None, socket.AF_INET)
                return hostname  # IPv4解析成功，返回原主机名
            except:
                # IPv4失败，尝试IPv6
                info = socket.getaddrinfo(hostname, None, socket.AF_INET6)
                if info:
                    ipv6_addr = str(info[0][4][0])
                    print(f"   🌐 检测到IPv6地址: {ipv6_addr}")
                    return ipv6_addr
                return hostname
        except Exception as e:
            print(f"   ⚠️ DNS解析警告: {e}")
            return hostname
    
    def test_database_connection(self) -> bool:
        """测试数据库连接"""
        print("🔗 测试数据库连接...")
        
        try:
            # 隐藏密码显示
            safe_config = self.db_config.copy()
            safe_config['password'] = '***'
            print(f"   连接信息: {safe_config}")
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 测试基本查询
            cursor.execute("SELECT version(), current_database(), current_user, now();")
            result = cursor.fetchone()
            
            if result:
                details = {
                    'version': result['version'],
                    'database': result['current_database'],
                    'user': result['current_user'],
                    'server_time': str(result['now'])
                }
                
                self.add_result('database_connection', True, 
                              f"✅ 数据库连接成功: {result['current_database']}", details)
                print(f"   ✅ 连接成功: PostgreSQL {result['version'].split()[1]}")
                print(f"   📊 数据库: {result['current_database']}")
                print(f"   👤 用户: {result['current_user']}")
                
                cursor.close()
                conn.close()
                return True
            else:
                self.add_result('database_connection', False, "❌ 数据库查询返回空结果")
                return False
                
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            self.add_result('database_connection', False, f"❌ 数据库连接失败: {error_msg}")
            print(f"   ❌ 连接失败: {error_msg}")
            return False
        except Exception as e:
            self.add_result('database_connection', False, f"❌ 数据库连接异常: {str(e)}")
            print(f"   ❌ 连接异常: {str(e)}")
            return False
    
    def test_schema_access(self) -> bool:
        """测试模式访问权限"""
        print("🏗️ 测试模式访问权限...")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 检查可访问的模式
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_owner = current_user 
                   OR schema_name IN ('public', 'flowslide')
                ORDER BY schema_name;
            """)
            schemas = [row['schema_name'] for row in cursor.fetchall()]
            
            # 检查当前搜索路径
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()['search_path']
            
            details = {
                'accessible_schemas': schemas,
                'search_path': search_path,
                'flowslide_schema_exists': 'flowslide' in schemas
            }
            
            if 'flowslide' in schemas:
                self.add_result('schema_access', True, 
                              f"✅ 模式访问正常，可访问模式: {', '.join(schemas)}", details)
                print(f"   ✅ 可访问模式: {', '.join(schemas)}")
                print(f"   🔍 搜索路径: {search_path}")
            else:
                self.add_result('schema_access', False, 
                              f"⚠️ flowslide 模式不存在或无权限", details, warning=True)
                print("   ⚠️ flowslide 模式不存在或无权限")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            self.add_result('schema_access', False, f"❌ 模式检查失败: {str(e)}")
            print(f"   ❌ 模式检查失败: {str(e)}")
            return False
    
    def test_table_operations(self) -> bool:
        """测试表操作权限"""
        print("📋 测试表操作权限...")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            test_table = f"health_check_test_{int(time.time())}"
            operations = {}
            
            try:
                # 创建测试表
                create_sql = f"""
                CREATE TABLE IF NOT EXISTS {test_table} (
                    id SERIAL PRIMARY KEY,
                    test_data TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """
                cursor.execute(create_sql)
                conn.commit()
                operations['create'] = True
                print(f"   ✅ 创建表权限: 正常")
                
                # 插入测试数据
                cursor.execute(f"INSERT INTO {test_table} (test_data) VALUES (%s);", 
                             ("健康检查测试数据",))
                conn.commit()
                operations['insert'] = True
                print(f"   ✅ 插入数据权限: 正常")
                
                # 查询测试数据
                cursor.execute(f"SELECT * FROM {test_table} LIMIT 1;")
                result = cursor.fetchone()
                operations['select'] = bool(result)
                print(f"   ✅ 查询数据权限: 正常")
                
                # 更新测试数据
                cursor.execute(f"UPDATE {test_table} SET test_data = %s WHERE id = %s;", 
                             ("更新的测试数据", result['id']))
                conn.commit()
                operations['update'] = cursor.rowcount > 0
                print(f"   ✅ 更新数据权限: 正常")
                
                # 删除测试数据
                cursor.execute(f"DELETE FROM {test_table} WHERE id = %s;", (result['id'],))
                conn.commit()
                operations['delete'] = cursor.rowcount > 0
                print(f"   ✅ 删除数据权限: 正常")
                
            finally:
                # 清理测试表
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {test_table};")
                    conn.commit()
                    operations['drop'] = True
                    print(f"   ✅ 删除表权限: 正常")
                except:
                    operations['drop'] = False
            
            all_passed = all(operations.values())
            self.add_result('table_operations', all_passed, 
                          f"{'✅' if all_passed else '❌'} 表操作权限测试", operations)
            
            cursor.close()
            conn.close()
            return all_passed
            
        except Exception as e:
            self.add_result('table_operations', False, f"❌ 表操作测试失败: {str(e)}")
            print(f"   ❌ 表操作测试失败: {str(e)}")
            return False
    
    def test_api_connection(self) -> bool:
        """测试 API 连接（如果配置了的话）"""
        print("🌐 测试 API 连接...")
        
        if not self.api_url or not self.api_anon_key:
            self.add_result('api_connection', False, 
                          "❌ API 配置缺失 (API_URL 或 API_ANON_KEY)", warning=True)
            print("   ⚠️ API 配置缺失，跳过 API 测试")
            return False
        
        try:
            # 测试 API 健康状态
            health_url = f"{self.api_url}/rest/v1/"
            headers = {
                'apikey': self.api_anon_key,
                'Authorization': f'Bearer {self.api_anon_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(health_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                self.add_result('api_connection', True, 
                              f"✅ API 连接成功: {self.api_url}")
                print(f"   ✅ API 连接成功: {response.status_code}")
                return True
            else:
                self.add_result('api_connection', False, 
                              f"❌ API 响应异常: {response.status_code}")
                print(f"   ❌ API 响应异常: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.add_result('api_connection', False, f"❌ API 连接失败: {str(e)}")
            print(f"   ❌ API 连接失败: {str(e)}")
            return False
    
    def test_storage_access(self) -> bool:
        """测试存储访问（如果配置了的话）"""
        print("💾 测试存储访问...")
        
        if not self.api_url or not self.api_service_key:
            self.add_result('storage_access', False, 
                          "❌ 存储测试需要 API_SERVICE_KEY", warning=True)
            print("   ⚠️ 存储测试需要 API_SERVICE_KEY，跳过存储测试")
            return False
        
        try:
            # 测试存储桶列表（支持Supabase风格的REST API）
            if self.storage_provider.lower() in ['supabase', 'postgresql', 'postgres']:
                storage_url = f"{self.api_url}/storage/v1/bucket"
                headers = {
                    'apikey': self.api_service_key,
                    'Authorization': f'Bearer {self.api_service_key}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.get(storage_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    buckets = response.json()
                    bucket_names = [bucket.get('name', 'unknown') for bucket in buckets]
                    
                    # 如果没有指定存储桶，只检查API可用性
                    if not self.storage_bucket:
                        details = {
                            'available_buckets': bucket_names,
                            'target_bucket': 'none_specified',
                            'api_accessible': True
                        }
                        self.add_result('storage_access', True, 
                                      f"✅ 存储API可访问，发现 {len(bucket_names)} 个存储桶", details)
                        print(f"   ✅ 存储API可访问，发现存储桶: {bucket_names}")
                        return True
                    
                    bucket_exists = self.storage_bucket in bucket_names
                    
                    details = {
                        'available_buckets': bucket_names,
                        'target_bucket': self.storage_bucket,
                        'bucket_exists': bucket_exists
                    }
                    
                    if bucket_exists:
                        self.add_result('storage_access', True, 
                                      f"✅ 存储访问正常，目标桶存在: {self.storage_bucket}", details)
                        print(f"   ✅ 存储桶存在: {self.storage_bucket}")
                    else:
                        self.add_result('storage_access', False, 
                                      f"⚠️ 目标存储桶不存在: {self.storage_bucket}", details, warning=True)
                        print(f"   ⚠️ 目标存储桶不存在: {self.storage_bucket}")
                        print(f"   📂 可用存储桶: {', '.join(bucket_names)}")
                    
                    return bucket_exists
                else:
                    self.add_result('storage_access', False, 
                                  f"❌ 存储API响应异常: {response.status_code}")
                    print(f"   ❌ 存储API响应异常: {response.status_code}")
                    return False
            else:
                self.add_result('storage_access', False, 
                              f"⚠️ 存储提供商 '{self.storage_provider}' 不支持API测试", warning=True)
                print(f"   ⚠️ 存储提供商 '{self.storage_provider}' 不支持API测试")
                return False
                
        except requests.exceptions.RequestException as e:
            self.add_result('storage_access', False, f"❌ 存储连接失败: {str(e)}")
            print(f"   ❌ 存储连接失败: {str(e)}")
            return False
    
    def run_performance_test(self) -> bool:
        """运行性能测试"""
        print("⚡ 运行性能测试...")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 连接延迟测试
            start_time = time.time()
            cursor.execute("SELECT 1;")
            cursor.fetchone()
            connection_latency = (time.time() - start_time) * 1000
            
            # 简单查询性能测试
            start_time = time.time()
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables;")
            cursor.fetchone()
            query_time = (time.time() - start_time) * 1000
            
            # 并发连接测试
            max_connections = None
            try:
                cursor.execute("SHOW max_connections;")
                max_connections = int(cursor.fetchone()['max_connections'])
            except:
                pass
            
            performance_data = {
                'connection_latency_ms': round(connection_latency, 2),
                'simple_query_time_ms': round(query_time, 2),
                'max_connections': max_connections
            }
            
            # 性能评估
            is_good_performance = connection_latency < 100 and query_time < 50
            
            self.add_result('performance_test', is_good_performance, 
                          f"{'✅' if is_good_performance else '⚠️'} 性能测试完成", 
                          performance_data, warning=not is_good_performance)
            
            print(f"   📊 连接延迟: {performance_data['connection_latency_ms']}ms")
            print(f"   📊 查询时间: {performance_data['simple_query_time_ms']}ms")
            if max_connections:
                print(f"   📊 最大连接数: {max_connections}")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            self.add_result('performance_test', False, f"❌ 性能测试失败: {str(e)}")
            print(f"   ❌ 性能测试失败: {str(e)}")
            return False
    
    def save_report(self) -> Optional[str]:
        """保存检查报告"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 根据实际数据库类型生成报告文件名
            db_type = "postgresql"
            if self.storage_provider.lower() == 'supabase':
                db_type = "supabase"
            elif "postgres" in self.db_config.get('host', '').lower():
                db_type = "postgres"
            
            filename = f"{db_type}_health_report_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            
            return filename
        except Exception as e:
            print(f"❌ 保存报告失败: {str(e)}")
            return None
    
    def print_summary(self):
        """打印检查总结"""
        print("\n" + "="*50)
        print("📊 健康检查总结")
        print("="*50)
        
        summary = self.results['summary']
        print(f"🔍 总检查项: {summary['total']}")
        print(f"✅ 通过: {summary['passed']}")
        print(f"❌ 失败: {summary['failed']}")
        print(f"⚠️ 警告: {summary['warnings']}")
        
        # 计算健康分数
        if summary['total'] > 0:
            health_score = (summary['passed'] / summary['total']) * 100
            print(f"💯 健康分数: {health_score:.1f}%")
            
            if health_score >= 90:
                print("🎉 数据库状态: 优秀")
            elif health_score >= 70:
                print("👍 数据库状态: 良好")
            elif health_score >= 50:
                print("⚠️ 数据库状态: 需要注意")
            else:
                print("🚨 数据库状态: 需要紧急处理")
        
        print("="*50)
    
    def run_all_checks(self) -> bool:
        """运行所有健康检查"""
        # 根据配置确定数据库类型
        if self.storage_provider.lower() == 'supabase':
            db_name = "Supabase PostgreSQL"
        elif "supabase" in self.db_config.get('host', '').lower():
            db_name = "Supabase PostgreSQL"
        else:
            db_name = "PostgreSQL"
            
        print(f"🚀 开始 {db_name} 数据库健康检查...")
        print("="*50)
        
        # 必要检查
        checks = [
            self.test_database_connection,
            self.test_schema_access,
            self.test_table_operations,
            self.test_api_connection,
            self.test_storage_access,
            self.run_performance_test
        ]
        
        success_count = 0
        for check in checks:
            try:
                if check():
                    success_count += 1
                print()  # 空行分隔
            except Exception as e:
                print(f"❌ 检查过程异常: {str(e)}\n")
        
        # 打印总结
        self.print_summary()
        
        # 保存报告
        report_file = self.save_report()
        if report_file:
            print(f"📄 详细报告已保存: {report_file}")
        
        return success_count >= len(checks) * 0.7  # 70% 通过率认为整体健康


def main():
    """主函数"""
    print("🏥 FlowSlide PostgreSQL 数据库健康检查工具")
    print("版本: 2.0.0 | 支持 PostgreSQL 及其衍生产品（如 Supabase）")
    print()
    
    # 检查必要的环境变量
    required_vars = ['DATABASE_URL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars and not all(os.getenv(var) for var in ['DB_HOST', 'DB_USER', 'DB_PASSWORD']):
        print("❌ 缺少必要的环境变量:")
        print("   请设置 DATABASE_URL 或 (DB_HOST, DB_USER, DB_PASSWORD)")
        print()
        print("示例配置:")
        print("DATABASE_URL=postgresql://user:pass@host:port/dbname?sslmode=require")
        print("或者:")
        print("DB_HOST=your-host")
        print("DB_PORT=your-port")
        print("DB_USER=your-user")
        print("DB_PASSWORD=your-password")
        sys.exit(1)
    
    # 运行健康检查
    checker = PostgreSQLHealthChecker()
    success = checker.run_all_checks()
    
    print(f"\n🎯 检查完成! {'成功' if success else '发现问题'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
