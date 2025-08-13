#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库诊断工具 - 详细分析数据库性能和问题
Database Diagnosis Tool - Detailed analysis of database performance and issues

作者: AI Assistant
版本: 1.0.0
日期: 2025-08-13
"""

import os
import sys
import time
import json
import psycopg2
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('database_diagnosis.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class DatabaseDiagnosis:
    """数据库诊断类"""
    
    def __init__(self):
        """初始化诊断工具"""
        self.db_config = {
            'host': os.getenv('DB_HOST', 'aws-0-ap-southeast-1.pooler.supabase.com'),
            'port': int(os.getenv('DB_PORT', 6543)),
            'database': os.getenv('DB_NAME', 'postgres'),
            'user': os.getenv('DB_USER', 'postgres.cweucknwqbtkyhsplbig'),
            'password': os.getenv('DB_PASSWORD', '')
        }
        self.connection: Optional[psycopg2.extensions.connection] = None
        self.diagnosis_results: Dict[str, Any] = {}
        
    def connect(self) -> bool:
        """连接到数据库"""
        try:
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
            logger.info("🔌 数据库连接已断开")
    
    def check_connection_metrics(self) -> Dict[str, Any]:
        """检查连接指标"""
        logger.info("🔍 检查连接指标...")
        metrics: Dict[str, Any] = {}
        
        try:
            if not self.connection:
                raise Exception("数据库未连接")
                
            cursor = self.connection.cursor()
            
            # 当前连接数
            cursor.execute("SELECT count(*) FROM pg_stat_activity;")
            result = cursor.fetchone()
            metrics['total_connections'] = result[0] if result else 0
            
            # 活跃连接数
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active';")
            result = cursor.fetchone()
            metrics['active_connections'] = result[0] if result else 0
            
            # 空闲连接数
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'idle';")
            result = cursor.fetchone()
            metrics['idle_connections'] = result[0] if result else 0
            
            # 最大连接数
            cursor.execute("SHOW max_connections;")
            result = cursor.fetchone()
            metrics['max_connections'] = int(result[0]) if result else 100
            
            # 连接使用率
            if metrics['max_connections'] > 0:
                metrics['connection_usage_percent'] = (metrics['total_connections'] / metrics['max_connections']) * 100
            else:
                metrics['connection_usage_percent'] = 0
            
            cursor.close()
            
            logger.info(f"📊 连接指标:")
            logger.info(f"   总连接数: {metrics['total_connections']}")
            logger.info(f"   活跃连接: {metrics['active_connections']}")
            logger.info(f"   空闲连接: {metrics['idle_connections']}")
            logger.info(f"   最大连接: {metrics['max_connections']}")
            logger.info(f"   使用率: {metrics['connection_usage_percent']:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ 连接指标检查失败: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def check_database_size(self) -> Dict[str, Any]:
        """检查数据库大小"""
        logger.info("💾 检查数据库大小...")
        size_info: Dict[str, Any] = {}
        
        try:
            if not self.connection:
                raise Exception("数据库未连接")
                
            cursor = self.connection.cursor()
            
            # 数据库总大小
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as db_size,
                       pg_database_size(current_database()) as db_size_bytes;
            """)
            result = cursor.fetchone()
            if result:
                size_info['database_size'] = result[0]
                size_info['database_size_bytes'] = result[1]
            
            # 表大小排行
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10;
            """)
            
            tables = []
            for row in cursor.fetchall():
                tables.append({
                    'schema': row[0],
                    'table': row[1],
                    'size': row[2],
                    'size_bytes': row[3]
                })
            
            size_info['largest_tables'] = tables
            cursor.close()
            
            logger.info(f"📊 数据库大小: {size_info.get('database_size', 'Unknown')}")
            logger.info("📊 最大的表:")
            for table in tables[:5]:
                logger.info(f"   {table['schema']}.{table['table']}: {table['size']}")
                
        except Exception as e:
            logger.error(f"❌ 数据库大小检查失败: {e}")
            size_info['error'] = str(e)
        
        return size_info
    
    def check_query_performance(self) -> Dict[str, Any]:
        """检查查询性能"""
        logger.info("⚡ 检查查询性能...")
        performance: Dict[str, Any] = {}
        
        try:
            if not self.connection:
                raise Exception("数据库未连接")
                
            cursor = self.connection.cursor()
            
            # 慢查询统计
            try:
                cursor.execute("""
                    SELECT 
                        query,
                        calls,
                        total_time,
                        mean_time,
                        max_time,
                        min_time
                    FROM pg_stat_statements 
                    WHERE query NOT LIKE '%pg_stat_statements%'
                    ORDER BY total_time DESC 
                    LIMIT 10;
                """)
                
                slow_queries = []
                for row in cursor.fetchall():
                    slow_queries.append({
                        'query': row[0][:100] + '...' if len(row[0]) > 100 else row[0],
                        'calls': row[1],
                        'total_time': round(row[2], 2),
                        'mean_time': round(row[3], 2),
                        'max_time': round(row[4], 2),
                        'min_time': round(row[5], 2)
                    })
                
                performance['slow_queries'] = slow_queries
                
            except Exception as e:
                logger.warning(f"⚠️ pg_stat_statements 不可用: {e}")
                performance['slow_queries'] = []
            
            # 锁等待检查
            cursor.execute("""
                SELECT count(*) as blocked_queries
                FROM pg_locks 
                WHERE NOT granted;
            """)
            result = cursor.fetchone()
            performance['blocked_queries'] = result[0] if result else 0
            
            # 活跃查询
            cursor.execute("""
                SELECT count(*) as active_queries
                FROM pg_stat_activity 
                WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%';
            """)
            result = cursor.fetchone()
            performance['active_queries'] = result[0] if result else 0
            
            cursor.close()
            
            logger.info(f"📊 性能指标:")
            logger.info(f"   活跃查询: {performance['active_queries']}")
            logger.info(f"   阻塞查询: {performance['blocked_queries']}")
            logger.info(f"   慢查询记录: {len(performance['slow_queries'])}")
            
        except Exception as e:
            logger.error(f"❌ 查询性能检查失败: {e}")
            performance['error'] = str(e)
        
        return performance
    
    def run_basic_diagnosis(self) -> Dict[str, Any]:
        """运行基础诊断（快速版本）"""
        logger.info("🔬 开始基础数据库诊断...")
        
        if not self.connect():
            return {'error': '无法连接到数据库'}
        
        start_time = time.time()
        
        # 执行基础诊断检查
        self.diagnosis_results = {
            'timestamp': datetime.now().isoformat(),
            'database_info': {
                'host': self.db_config['host'],
                'port': self.db_config['port'],
                'database': self.db_config['database']
            },
            'connection_metrics': self.check_connection_metrics(),
            'database_size': self.check_database_size(),
            'query_performance': self.check_query_performance()
        }
        
        end_time = time.time()
        self.diagnosis_results['diagnosis_duration'] = round(end_time - start_time, 2)
        
        self.disconnect()
        
        logger.info(f"✅ 基础诊断完成，耗时 {self.diagnosis_results['diagnosis_duration']} 秒")
        
        return self.diagnosis_results
    
    def save_diagnosis_report(self, filename: Optional[str] = None) -> str:
        """保存诊断报告"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"database_diagnosis_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.diagnosis_results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 诊断报告已保存: {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ 保存报告失败: {e}")
            return ""
    
    def print_summary(self):
        """打印诊断摘要"""
        if not self.diagnosis_results:
            logger.warning("⚠️ 没有诊断结果可显示")
            return
        
        print("\n" + "="*60)
        print("📊 数据库诊断摘要报告")
        print("="*60)
        
        # 连接信息
        conn_metrics = self.diagnosis_results.get('connection_metrics', {})
        if 'total_connections' in conn_metrics:
            print(f"\n🔌 连接状态:")
            print(f"   总连接数: {conn_metrics['total_connections']}")
            print(f"   活跃连接: {conn_metrics['active_connections']}")
            print(f"   连接使用率: {conn_metrics['connection_usage_percent']:.1f}%")
        
        # 数据库大小
        db_size = self.diagnosis_results.get('database_size', {})
        if 'database_size' in db_size:
            print(f"\n💾 数据库大小: {db_size['database_size']}")
        
        # 性能指标
        performance = self.diagnosis_results.get('query_performance', {})
        if 'active_queries' in performance:
            print(f"\n⚡ 性能状态:")
            print(f"   活跃查询: {performance['active_queries']}")
            print(f"   阻塞查询: {performance['blocked_queries']}")
        
        print(f"\n⏱️ 诊断耗时: {self.diagnosis_results['diagnosis_duration']} 秒")
        print("="*60)

def main():
    """主函数"""
    print("🔬 数据库诊断工具启动")
    print("Database Diagnosis Tool Started")
    
    # 检查环境变量
    required_env = ['DB_PASSWORD']
    missing_env = [env for env in required_env if not os.getenv(env)]
    
    if missing_env:
        logger.error(f"❌ 缺少环境变量: {', '.join(missing_env)}")
        logger.info("💡 请设置以下环境变量:")
        logger.info("   export DB_PASSWORD='your_password'")
        logger.info("   export DB_HOST='your_host'  # 可选")
        logger.info("   export DB_PORT='your_port'  # 可选")
        logger.info("   export DB_NAME='your_db'    # 可选")
        logger.info("   export DB_USER='your_user'  # 可选")
        sys.exit(1)
    
    # 运行诊断
    diagnosis = DatabaseDiagnosis()
    results = diagnosis.run_basic_diagnosis()
    
    if 'error' in results:
        logger.error(f"❌ 诊断失败: {results['error']}")
        sys.exit(1)
    
    # 显示结果
    diagnosis.print_summary()
    
    # 保存报告
    report_file = diagnosis.save_diagnosis_report()
    if report_file:
        logger.info(f"📄 详细报告: {report_file}")
    
    logger.info("🎉 数据库诊断完成!")

if __name__ == "__main__":
    main()
