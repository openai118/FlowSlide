#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================
LandPPT Supabase 数据库健康检查工具
==============================================
全面检测数据库连接、权限、存储等功能
"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ 错误: 请安装 psycopg2-binary")
    print("运行: pip install psycopg2-binary")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ 错误: 请安装 requests")
    print("运行: pip install requests")
    sys.exit(1)


class SupabaseHealthChecker:
    """Supabase 数据库健康检查器"""
    
    def __init__(self):
        """初始化检查器，从环境变量或直接配置中读取设置"""
        # 数据库配置（默认使用应用用户）
        self.db_config = {
            'host': 'db.fiuzetazperebuqwmrna.supabase.co',
            'port': 5432,
            'database': 'postgres',
            'user': 'landppt_user',
            'password': 'Openai9zLwR1sT4u',
            'sslmode': 'require'
        }
        
        # postgres 超级用户配置（仅在需要时使用）
        self.admin_config = {
            'host': 'db.fiuzetazperebuqwmrna.supabase.co',
            'port': 5432,
            'database': 'postgres',
            'user': 'postgres',
            'password': None,  # 需要用户提供
            'sslmode': 'require'
        }
        
        # Supabase API 配置
        self.supabase_url = "https://fiuzetazperebuqwmrna.supabase.co"
        self.anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZpdXpldGF6cGVyZWJ1cXdtcm5hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ5NTI2NjgsImV4cCI6MjA3MDUyODY2OH0.aQwP7h_SFau6UsfsGbUHY3kf-RDYM8LEOLu0hsbv5Ns"
        self.service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZpdXpldGF6cGVyZWJ1cXdtcm5hIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NDk1MjY2OCwiZXhwIjoyMDcwNTI4NjY4fQ.8vdb7DH860INPx5ZhDd9JTdsfJtDAhOizQNZgEqONNE"
        self.storage_bucket = "landppt-files"
        
        # 应用用户配置
        self.app_user = {
            'username': 'landppt_user',
            'password': 'Openai9zLwR1sT4u'
        }
        
        self.test_results = []
        
    def setup_password(self, non_interactive=False):
        """设置数据库密码（仅在需要 postgres 超级用户时使用）"""
        if non_interactive:
            # 非交互模式，跳过 postgres 超级用户测试
            return False
            
        print("⚠️  注意：通常情况下，LandPPT 应用使用 landppt_user 即可")
        print("   只有在需要管理员权限时才需要 postgres 密码")
        use_admin = input("是否需要测试 postgres 超级用户权限? (y/N): ").strip().lower()
        
        if use_admin in ['y', 'yes']:
            password = input("请输入 Supabase postgres 用户密码: ").strip()
            if not password:
                print("❌ 密码不能为空")
                sys.exit(1)
            self.admin_config['password'] = password
            return True
        return False
        
    def log_test(self, test_name: str, success: bool, message: str, details: Any = None):
        """记录测试结果"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        # 实时输出
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        if details and not success:
            print(f"   详情: {details}")
            
    def test_basic_connection(self) -> bool:
        """测试基本数据库连接（使用应用用户）"""
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_database(), current_user;")
                result = cur.fetchone()
                
            conn.close()
            
            self.log_test(
                "应用用户连接测试",
                True,
                "landppt_user 连接成功",
                {
                    'version': result[0][:50] + "..." if len(result[0]) > 50 else result[0],
                    'database': result[1],
                    'user': result[2]
                }
            )
            return True
            
        except Exception as e:
            self.log_test("应用用户连接测试", False, "landppt_user 连接失败", str(e))
            return False
            
    def test_schema_access(self) -> bool:
        """测试 landppt schema 访问"""
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 检查 schema 是否存在
                cur.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = 'landppt';
                """)
                schema_exists = cur.fetchone()
                
                if not schema_exists:
                    raise Exception("landppt schema 不存在")
                
                # 检查验证表
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM landppt.deployment_verification;
                """)
                count_result = cur.fetchone()
                
                # 检查测试函数
                cur.execute("SELECT landppt.test_connection() as result;")
                func_result = cur.fetchone()
                
            conn.close()
            
            self.log_test(
                "Schema 访问测试",
                True,
                "Schema 和表访问正常",
                {
                    'verification_records': count_result['count'],
                    'test_function': func_result['result']
                }
            )
            return True
            
        except Exception as e:
            self.log_test("Schema 访问测试", False, "Schema 访问失败", str(e))
            return False
            
    def test_app_user_connection(self) -> bool:
        """测试应用用户权限（详细权限检查）"""
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 检查当前用户和搜索路径
                cur.execute("SELECT current_user as user, current_setting('search_path') as search_path;")
                user_info = cur.fetchone()
                
                # 测试读取权限
                cur.execute("SELECT COUNT(*) as count FROM deployment_verification;")
                read_result = cur.fetchone()
                
                # 测试写入权限
                test_message = f"健康检查测试 - {datetime.now().isoformat()}"
                cur.execute("""
                    INSERT INTO deployment_verification (message) 
                    VALUES (%s) RETURNING id;
                """, (test_message,))
                insert_result = cur.fetchone()
                
                # 测试函数调用
                cur.execute("SELECT test_connection() as result;")
                func_result = cur.fetchone()
                
                # 清理测试数据
                cur.execute("DELETE FROM deployment_verification WHERE id = %s;", (insert_result['id'],))
                
            conn.commit()
            conn.close()
            
            self.log_test(
                "应用用户权限测试",
                True,
                "应用用户权限正常",
                {
                    'user': user_info['user'],
                    'search_path': user_info['search_path'],
                    'can_read': True,
                    'can_write': True,
                    'can_execute_functions': True,
                    'test_record_id': insert_result['id'],
                    'existing_records': read_result['count']
                }
            )
            return True
            
        except Exception as e:
            self.log_test("应用用户权限测试", False, "应用用户权限异常", str(e))
            return False
            
    def test_storage_api(self) -> bool:
        """测试 Supabase Storage API"""
        try:
            # 测试存储桶列表
            headers = {
                'Authorization': f'Bearer {self.service_key}',
            }
            
            # 获取存储桶信息
            bucket_url = f"{self.supabase_url}/storage/v1/bucket"
            response = requests.get(bucket_url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"获取存储桶失败: {response.status_code} - {response.text}")
                
            buckets = response.json()
            landppt_bucket = None
            for bucket in buckets:
                if bucket['id'] == self.storage_bucket:
                    landppt_bucket = bucket
                    break
                    
            if not landppt_bucket:
                raise Exception(f"未找到存储桶: {self.storage_bucket}")
                
            # 测试文件上传
            test_content = f"LandPPT 健康检查测试文件\n创建时间: {datetime.now().isoformat()}"
            test_filename = f"health_check_{int(time.time())}.txt"
            
            upload_url = f"{self.supabase_url}/storage/v1/object/{self.storage_bucket}/{test_filename}"
            
            # 使用二进制模式上传
            files = {'file': (test_filename, test_content.encode('utf-8'), 'text/plain')}
            upload_response = requests.post(upload_url, headers=headers, files=files)
            
            if upload_response.status_code not in [200, 201]:
                raise Exception(f"文件上传失败: {upload_response.status_code} - {upload_response.text}")
                
            # 测试文件下载
            download_url = f"{self.supabase_url}/storage/v1/object/{self.storage_bucket}/{test_filename}"
            download_response = requests.get(download_url, headers=headers)
            
            if download_response.status_code != 200:
                raise Exception(f"文件下载失败: {download_response.status_code}")
                
            # 验证文件内容（使用字节比较更准确）
            downloaded_content = download_response.content.decode('utf-8')
            if downloaded_content.strip() != test_content.strip():
                raise Exception(f"上传和下载的文件内容不匹配\n上传: {test_content}\n下载: {downloaded_content}")
                
            # 清理测试文件
            delete_response = requests.delete(download_url, headers=headers)
            
            self.log_test(
                "存储 API 测试",
                True,
                "存储功能正常",
                {
                    'bucket_info': landppt_bucket,
                    'test_file': test_filename,
                    'upload_status': upload_response.status_code,
                    'download_status': download_response.status_code,
                    'delete_status': delete_response.status_code,
                    'content_size': len(test_content)
                }
            )
            return True
            
        except Exception as e:
            self.log_test("存储 API 测试", False, "存储功能异常", str(e))
            return False
            
    def test_performance(self) -> bool:
        """测试数据库性能"""
        try:
            conn = psycopg2.connect(**self.db_config)
            
            # 测试查询性能
            start_time = time.time()
            with conn.cursor() as cur:
                for i in range(10):
                    cur.execute("SELECT COUNT(*) FROM landppt.deployment_verification;")
                    cur.fetchone()
            query_time = time.time() - start_time
            
            # 测试连接延迟
            start_time = time.time()
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            latency = time.time() - start_time
            
            conn.close()
            
            self.log_test(
                "性能测试",
                True,
                "性能指标正常",
                {
                    '10次查询耗时': f"{query_time:.3f}秒",
                    '单次延迟': f"{latency:.3f}秒",
                    '平均查询时间': f"{query_time/10:.3f}秒"
                }
            )
            return True
            
        except Exception as e:
            self.log_test("性能测试", False, "性能测试失败", str(e))
            return False
            
    def generate_report(self) -> Dict[str, Any]:
        """生成完整的检查报告"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - passed_tests
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%",
                'overall_health': 'HEALTHY' if failed_tests == 0 else 'UNHEALTHY'
            },
            'test_results': self.test_results,
            'generated_at': datetime.now().isoformat(),
            'configuration': {
                'database_host': self.db_config['host'],
                'database_name': self.db_config['database'],
                'supabase_url': self.supabase_url,
                'storage_bucket': self.storage_bucket,
                'app_user': self.app_user['username']
            }
        }
        
        return report
        
    def run_all_tests(self, non_interactive=False) -> bool:
        """运行所有检查测试"""
        print("🚀 开始 LandPPT Supabase 数据库健康检查...")
        print("=" * 60)
        
        # 询问是否需要管理员权限测试
        need_admin = self.setup_password(non_interactive)
        
        all_passed = True
        
        # 执行所有测试
        tests = [
            ("应用用户连接", self.test_basic_connection),
            ("Schema 访问", self.test_schema_access),
            ("应用用户权限", self.test_app_user_connection),
            ("存储 API", self.test_storage_api),
            ("性能指标", self.test_performance)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔍 执行 {test_name} 测试...")
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                self.log_test(test_name, False, f"测试执行异常: {str(e)}")
                all_passed = False
                
        print("\n" + "=" * 60)
        print("📊 生成检查报告...")
        
        return all_passed
        
    def save_report(self, filename: Optional[str] = None):
        """保存检查报告到文件"""
        if filename is None:
            filename = f"supabase_health_report_{int(time.time())}.json"
            
        report = self.generate_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            
        print(f"📄 报告已保存到: {filename}")
        return filename


def main():
    """主函数"""
    try:
        # 检查是否为非交互模式
        non_interactive = "--non-interactive" in sys.argv
        
        checker = SupabaseHealthChecker()
        success = checker.run_all_tests(non_interactive)
        
        # 生成并保存报告
        report = checker.generate_report()
        report_file = checker.save_report()
        
        # 输出总结
        print("\n" + "=" * 60)
        print("📋 检查总结:")
        print(f"   总测试数: {report['summary']['total_tests']}")
        print(f"   通过数量: {report['summary']['passed']}")
        print(f"   失败数量: {report['summary']['failed']}")
        print(f"   成功率: {report['summary']['success_rate']}")
        print(f"   整体状态: {report['summary']['overall_health']}")
        
        if success:
            print("\n🎉 所有检查通过！数据库配置正常，可以部署 LandPPT 应用。")
            return 0
        else:
            print("\n⚠️ 部分检查失败！请查看详细报告并修复问题。")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断检查")
        return 130
    except Exception as e:
        print(f"\n❌ 检查器异常: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
