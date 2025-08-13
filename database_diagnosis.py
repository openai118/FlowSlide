#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库诊断工具 - 详细分析数据库性能和问题
Database Diagnosis Tool - Detailed analysis of database performance and issues

作者: AI Assistant
版本: 2.0.0 - 支持 DATABASE_URL 配置
日期: 2025-08-13
"""

import os
import sys
import time
import json
import psycopg2
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('database_diagnosis.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class DatabaseDiagnosis:
    """数据库诊断工具"""
    
    def __init__(self):
        """初始化诊断工具"""
        # 优先使用 DATABASE_URL，如果不存在则使用分离的环境变量
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # 解析 DATABASE_URL
            self.db_config = self._parse_database_url(database_url)
        else:
            # 使用分离的环境变量（保持向后兼容）
            self.db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', ''),
                'sslmode': 'require'
            }
        
        self.connection = None
        self.diagnosis_results = {}
    
    def _parse_database_url(self, url):
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
            logger.error(f"❌ 解析 DATABASE_URL 失败: {e}")
            sys.exit(1)
    
    def connect(self):
        """连接到数据库"""
        try:
            logger.info("🔗 正在连接数据库...")
            
            # 隐藏密码显示
            safe_config = self.db_config.copy()
            safe_config['password'] = '***'
            logger.info(f"连接配置: {safe_config}")
            
            self.connection = psycopg2.connect(**self.db_config)
            if self.connection:
                self.connection.autocommit = True
                logger.info("✅ 数据库连接成功")
                return True
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            self.connection = None
        return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("🔒 数据库连接已关闭")
    
    def test_basic_connectivity(self):
        """测试基本连接性"""
        logger.info("🔍 测试基本连接性...")
        
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT version(), current_database(), current_user, now();")
            result = cursor.fetchone()
            
            if result:
                self.diagnosis_results['connectivity'] = {
                    'status': 'success',
                    'version': result[0],
                    'database': result[1],
                    'user': result[2],
                    'timestamp': str(result[3])
                }
                logger.info(f"✅ 连接测试成功 - 数据库: {result[1]}, 用户: {result[2]}")
                return True
            
        except Exception as e:
            self.diagnosis_results['connectivity'] = {
                'status': 'failed',
                'error': str(e)
            }
            logger.error(f"❌ 连接测试失败: {e}")
        
        return False
    
    def analyze_database_performance(self):
        """分析数据库性能"""
        logger.info("⚡ 分析数据库性能...")
        
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 获取数据库大小
            cursor.execute("""
                SELECT pg_database.datname,
                       pg_size_pretty(pg_database_size(pg_database.datname)) AS size
                FROM pg_database
                WHERE datname = current_database();
            """)
            db_size = cursor.fetchone()
            
            # 获取活跃连接数
            cursor.execute("""
                SELECT count(*) as active_connections,
                       max_conn.setting::int as max_connections,
                       (count(*)::float / max_conn.setting::float * 100)::numeric(5,2) as usage_percent
                FROM pg_stat_activity psa
                CROSS JOIN (SELECT setting FROM pg_settings WHERE name = 'max_connections') max_conn
                WHERE state = 'active';
            """)
            connection_stats = cursor.fetchone()
            
            # 获取缓存命中率
            cursor.execute("""
                SELECT sum(heap_blks_hit) as heap_hit,
                       sum(heap_blks_read) as heap_read,
                       round(sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100, 2) as cache_hit_ratio
                FROM pg_statio_user_tables;
            """)
            cache_stats = cursor.fetchone()
            
            performance_data = {
                'database_size': db_size[1] if db_size else 'Unknown',
                'active_connections': connection_stats[0] if connection_stats else 0,
                'max_connections': connection_stats[1] if connection_stats else 0,
                'connection_usage_percent': float(connection_stats[2]) if connection_stats and connection_stats[2] else 0,
                'cache_hit_ratio': float(cache_stats[2]) if cache_stats and cache_stats[2] else 0
            }
            
            self.diagnosis_results['performance'] = performance_data
            
            logger.info(f"📊 数据库大小: {performance_data['database_size']}")
            logger.info(f"📊 活跃连接: {performance_data['active_connections']}/{performance_data['max_connections']} ({performance_data['connection_usage_percent']}%)")
            logger.info(f"📊 缓存命中率: {performance_data['cache_hit_ratio']}%")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 性能分析失败: {e}")
            self.diagnosis_results['performance'] = {'error': str(e)}
            return False
    
    def check_table_statistics(self):
        """检查表统计信息"""
        logger.info("📋 检查表统计信息...")
        
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 获取表的基本信息
            cursor.execute("""
                SELECT schemaname, tablename, 
                       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                       n_tup_ins as inserts,
                       n_tup_upd as updates,
                       n_tup_del as deletes,
                       n_live_tup as live_tuples,
                       n_dead_tup as dead_tuples
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10;
            """)
            
            tables = cursor.fetchall()
            
            table_stats = []
            for table in tables:
                table_stats.append({
                    'schema': table[0],
                    'table': table[1],
                    'size': table[2],
                    'inserts': table[3],
                    'updates': table[4],
                    'deletes': table[5],
                    'live_tuples': table[6],
                    'dead_tuples': table[7]
                })
            
            self.diagnosis_results['tables'] = table_stats
            
            logger.info(f"📊 找到 {len(table_stats)} 个用户表")
            for table in table_stats[:3]:  # 显示前3个最大的表
                logger.info(f"   📋 {table['schema']}.{table['table']}: {table['size']}, {table['live_tuples']} 活跃行")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 表统计检查失败: {e}")
            self.diagnosis_results['tables'] = {'error': str(e)}
            return False
    
    def analyze_slow_queries(self):
        """分析慢查询"""
        logger.info("🐌 分析慢查询...")
        
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 检查是否启用了pg_stat_statements扩展
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                );
            """)
            
            has_pg_stat_statements = cursor.fetchone()[0]
            
            if has_pg_stat_statements:
                # 获取最慢的查询
                cursor.execute("""
                    SELECT query, 
                           calls,
                           total_exec_time,
                           mean_exec_time,
                           max_exec_time,
                           rows
                    FROM pg_stat_statements
                    WHERE calls > 1
                    ORDER BY mean_exec_time DESC
                    LIMIT 5;
                """)
                
                slow_queries = cursor.fetchall()
                
                query_stats = []
                for query in slow_queries:
                    query_stats.append({
                        'query': query[0][:100] + '...' if len(query[0]) > 100 else query[0],
                        'calls': query[1],
                        'total_time': query[2],
                        'avg_time': query[3],
                        'max_time': query[4],
                        'rows': query[5]
                    })
                
                self.diagnosis_results['slow_queries'] = {
                    'enabled': True,
                    'queries': query_stats
                }
                
                logger.info(f"📊 找到 {len(query_stats)} 个慢查询记录")
                
            else:
                self.diagnosis_results['slow_queries'] = {
                    'enabled': False,
                    'message': 'pg_stat_statements 扩展未启用'
                }
                logger.info("⚠️ pg_stat_statements 扩展未启用，无法分析慢查询")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 慢查询分析失败: {e}")
            self.diagnosis_results['slow_queries'] = {'error': str(e)}
            return False
    
    def check_index_usage(self):
        """检查索引使用情况"""
        logger.info("🗂️ 检查索引使用情况...")
        
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 获取索引使用统计
            cursor.execute("""
                SELECT schemaname, tablename, indexname,
                       idx_tup_read, idx_tup_fetch,
                       pg_size_pretty(pg_relation_size(indexrelid)) as size
                FROM pg_stat_user_indexes
                ORDER BY idx_tup_read DESC
                LIMIT 10;
            """)
            
            indexes = cursor.fetchall()
            
            # 查找未使用的索引
            cursor.execute("""
                SELECT schemaname, tablename, indexname,
                       pg_size_pretty(pg_relation_size(indexrelid)) as size
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0 AND idx_tup_read = 0
                ORDER BY pg_relation_size(indexrelid) DESC;
            """)
            
            unused_indexes = cursor.fetchall()
            
            index_stats = {
                'used_indexes': [],
                'unused_indexes': []
            }
            
            for idx in indexes:
                index_stats['used_indexes'].append({
                    'schema': idx[0],
                    'table': idx[1],
                    'index': idx[2],
                    'reads': idx[3],
                    'fetches': idx[4],
                    'size': idx[5]
                })
            
            for idx in unused_indexes:
                index_stats['unused_indexes'].append({
                    'schema': idx[0],
                    'table': idx[1],
                    'index': idx[2],
                    'size': idx[3]
                })
            
            self.diagnosis_results['indexes'] = index_stats
            
            logger.info(f"📊 活跃索引: {len(index_stats['used_indexes'])}")
            logger.info(f"📊 未使用索引: {len(index_stats['unused_indexes'])}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 索引检查失败: {e}")
            self.diagnosis_results['indexes'] = {'error': str(e)}
            return False
    
    def generate_recommendations(self):
        """生成优化建议"""
        logger.info("💡 生成优化建议...")
        
        recommendations = []
        
        # 基于连接使用率的建议
        if 'performance' in self.diagnosis_results:
            perf = self.diagnosis_results['performance']
            
            if 'connection_usage_percent' in perf and perf['connection_usage_percent'] > 80:
                recommendations.append({
                    'type': 'warning',
                    'category': 'connections',
                    'message': f"连接使用率过高 ({perf['connection_usage_percent']}%)，建议优化连接池配置"
                })
            
            if 'cache_hit_ratio' in perf and perf['cache_hit_ratio'] < 95:
                recommendations.append({
                    'type': 'warning',
                    'category': 'cache',
                    'message': f"缓存命中率较低 ({perf['cache_hit_ratio']}%)，建议增加shared_buffers配置"
                })
        
        # 基于未使用索引的建议
        if 'indexes' in self.diagnosis_results:
            unused = self.diagnosis_results['indexes'].get('unused_indexes', [])
            if len(unused) > 0:
                recommendations.append({
                    'type': 'info',
                    'category': 'indexes',
                    'message': f"发现 {len(unused)} 个未使用的索引，考虑删除以节省空间"
                })
        
        # 基于表统计的建议
        if 'tables' in self.diagnosis_results:
            tables = self.diagnosis_results['tables']
            if isinstance(tables, list):
                for table in tables:
                    if table.get('dead_tuples', 0) > table.get('live_tuples', 0) * 0.1:
                        recommendations.append({
                            'type': 'warning',
                            'category': 'maintenance',
                            'message': f"表 {table['schema']}.{table['table']} 有较多死元组，建议运行 VACUUM"
                        })
        
        self.diagnosis_results['recommendations'] = recommendations
        
        logger.info(f"💡 生成了 {len(recommendations)} 条优化建议")
        for rec in recommendations:
            icon = "⚠️" if rec['type'] == 'warning' else "ℹ️"
            logger.info(f"   {icon} {rec['message']}")
    
    def save_diagnosis_report(self):
        """保存诊断报告"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"database_diagnosis_report_{timestamp}.json"
            
            report = {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'tool_version': '2.0.0',
                    'database_config': {
                        'host': self.db_config.get('host', ''),
                        'database': self.db_config.get('database', ''),
                        'user': self.db_config.get('user', '')
                    }
                },
                'diagnosis': self.diagnosis_results
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"📄 诊断报告已保存: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ 保存报告失败: {e}")
            return None
    
    def run_full_diagnosis(self):
        """运行完整诊断"""
        logger.info("🚀 开始数据库诊断...")
        logger.info("="*50)
        
        # 连接数据库
        if not self.connect():
            logger.error("❌ 无法连接数据库，诊断终止")
            return False
        
        try:
            # 运行各项检查
            checks = [
                self.test_basic_connectivity,
                self.analyze_database_performance,
                self.check_table_statistics,
                self.analyze_slow_queries,
                self.check_index_usage
            ]
            
            success_count = 0
            for check in checks:
                try:
                    if check():
                        success_count += 1
                    logger.info("-" * 30)
                except Exception as e:
                    logger.error(f"❌ 检查过程异常: {e}")
            
            # 生成建议
            self.generate_recommendations()
            
            logger.info("="*50)
            logger.info("📊 诊断总结")
            logger.info(f"✅ 完成检查: {success_count}/{len(checks)}")
            
            if 'recommendations' in self.diagnosis_results:
                rec_count = len(self.diagnosis_results['recommendations'])
                logger.info(f"💡 优化建议: {rec_count} 条")
            
            # 保存报告
            report_file = self.save_diagnosis_report()
            if report_file:
                logger.info(f"📄 详细报告: {report_file}")
            
            logger.info("🎉 数据库诊断完成!")
            
            return success_count >= len(checks) * 0.7
            
        finally:
            self.disconnect()


def main():
    """主函数"""
    logger.info("🏥 数据库诊断工具")
    logger.info("版本: 2.0.0 | 支持 DATABASE_URL 和环境变量配置")
    logger.info("")
    
    # 检查必要的环境变量
    database_url = os.getenv('DATABASE_URL')
    has_separate_vars = all(os.getenv(var) for var in ['DB_HOST', 'DB_USER', 'DB_PASSWORD'])
    
    if not database_url and not has_separate_vars:
        logger.error("❌ 缺少必要的环境变量:")
        logger.error("   请设置 DATABASE_URL 或 (DB_HOST, DB_USER, DB_PASSWORD)")
        logger.error("")
        logger.error("示例配置:")
        logger.error("DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require")
        logger.error("或者:")
        logger.error("DB_HOST=your-host")
        logger.error("DB_USER=your-user") 
        logger.error("DB_PASSWORD=your-password")
        sys.exit(1)
    
    # 运行诊断
    diagnosis = DatabaseDiagnosis()
    success = diagnosis.run_full_diagnosis()
    
    logger.info(f"\n🎯 诊断完成! {'成功' if success else '发现问题'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
