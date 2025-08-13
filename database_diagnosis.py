#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================
LandPPT 数据库连接诊断工具
==============================================
详细诊断连接问题
"""

import sys
import traceback
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ 请安装: pip install psycopg2-binary")
    sys.exit(1)

def diagnose_connection():
    """诊断数据库连接问题"""
    print("🔧 LandPPT 数据库连接诊断")
    print("=" * 50)
    
    # 测试配置
    configs = [
        {
            'name': 'landppt_user (应用用户)',
            'config': {
                'host': 'db.fiuzetazperebuqwmrna.supabase.co',
                'port': 5432,
                'database': 'postgres',
                'user': 'landppt_user',
                'password': 'Openai9zLwR1sT4u',
                'sslmode': 'require'
            }
        }
    ]
    
    # 如果用户想测试 postgres 用户
    test_postgres = input("是否也测试 postgres 超级用户? (y/N): ").strip().lower()
    if test_postgres in ['y', 'yes']:
        postgres_password = input("请输入 postgres 密码: ").strip()
        if postgres_password:
            configs.append({
                'name': 'postgres (超级用户)',
                'config': {
                    'host': 'db.fiuzetazperebuqwmrna.supabase.co',
                    'port': 5432,
                    'database': 'postgres',
                    'user': 'postgres',
                    'password': postgres_password,
                    'sslmode': 'require'
                }
            })
    
    print(f"\n开始测试 {len(configs)} 个配置...")
    print("-" * 50)
    
    for test_config in configs:
        print(f"\n🔍 测试 {test_config['name']}:")
        print(f"   主机: {test_config['config']['host']}")
        print(f"   用户: {test_config['config']['user']}")
        print(f"   数据库: {test_config['config']['database']}")
        
        try:
            # 基本连接测试
            print("   ⏳ 尝试连接...")
            conn = psycopg2.connect(**test_config['config'])
            print("   ✅ 连接成功")
            
            # 基本查询测试
            print("   ⏳ 测试基本查询...")
            with conn.cursor() as cur:
                cur.execute("SELECT current_user, current_database(), version();")
                result = cur.fetchone()
                print(f"   ✅ 当前用户: {result[0]}")
                print(f"   ✅ 当前数据库: {result[1]}")
                print(f"   ✅ 版本: {result[2][:50]}...")
            
            # 如果是 landppt_user，测试应用相关功能
            if test_config['config']['user'] == 'landppt_user':
                print("   ⏳ 测试 landppt 应用功能...")
                
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 检查搜索路径
                    cur.execute("SELECT current_setting('search_path') as search_path;")
                    search_path_result = cur.fetchone()
                    search_path = search_path_result['search_path']
                    print(f"   ✅ 搜索路径: {search_path}")
                    
                    # 检查 schema 访问
                    cur.execute("""
                        SELECT schema_name 
                        FROM information_schema.schemata 
                        WHERE schema_name = 'landppt';
                    """)
                    schema_exists = cur.fetchone()
                    if schema_exists:
                        print("   ✅ landppt schema 存在")
                    else:
                        print("   ❌ landppt schema 不存在")
                        continue
                    
                    # 检查表访问
                    cur.execute("SELECT COUNT(*) as count FROM deployment_verification;")
                    count_result = cur.fetchone()
                    count = count_result['count']
                    print(f"   ✅ deployment_verification 表访问正常，有 {count} 条记录")
                    
                    # 测试函数
                    cur.execute("SELECT test_connection() as result;")
                    func_result = cur.fetchone()
                    func_text = func_result['result']
                    print(f"   ✅ test_connection() 函数正常: {func_text[:50]}...")
                    
                    # 测试写入
                    test_msg = f"诊断测试 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    cur.execute("INSERT INTO deployment_verification (message) VALUES (%s) RETURNING id;", (test_msg,))
                    insert_id = cur.fetchone()['id']
                    print(f"   ✅ 写入测试成功，ID: {insert_id}")
                    
                    # 清理测试数据
                    cur.execute("DELETE FROM deployment_verification WHERE id = %s;", (insert_id,))
                    print("   ✅ 测试数据已清理")
                    
            conn.commit()
            conn.close()
            print(f"   🎉 {test_config['name']} 所有测试通过!")
            
        except psycopg2.OperationalError as e:
            print(f"   ❌ 连接失败: {e}")
            if "authentication failed" in str(e):
                print("   💡 提示: 密码错误")
            elif "could not connect" in str(e):
                print("   💡 提示: 网络连接问题或主机不可达")
            elif "database" in str(e) and "does not exist" in str(e):
                print("   💡 提示: 数据库不存在")
        except psycopg2.ProgrammingError as e:
            print(f"   ❌ SQL 错误: {e}")
            if "permission denied" in str(e):
                print("   💡 提示: 权限不足")
            elif "does not exist" in str(e):
                print("   💡 提示: 对象不存在（表、函数、schema等）")
        except Exception as e:
            print(f"   ❌ 其他错误: {e}")
            print(f"   详细错误信息:")
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("🏁 诊断完成")
    
    # 给出建议
    print("\n💡 建议:")
    print("1. 如果 landppt_user 连接失败，请检查:")
    print("   - 用户是否已创建 (运行初始化 SQL)")
    print("   - 密码是否正确")
    print("   - 网络连接是否正常")
    print("\n2. 如果连接成功但功能测试失败，请检查:")
    print("   - landppt schema 是否已创建")
    print("   - 权限是否正确设置")
    print("   - 表和函数是否已创建")


if __name__ == "__main__":
    try:
        diagnose_connection()
    except KeyboardInterrupt:
        print("\n\n⏹️ 诊断被中断")
    except Exception as e:
        print(f"\n❌ 诊断工具异常: {e}")
        traceback.print_exc()
