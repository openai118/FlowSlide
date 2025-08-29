#!/usr/bin/env python3
"""
创建关键配置数据表的脚本
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from src.flowslide.database.models import Base, SystemConfig, AIProviderConfig
from src.flowslide.core.simple_config import LOCAL_DATABASE_URL

def create_config_tables():
    """创建配置相关的数据库表"""
    print("🔧 创建关键配置数据表...")

    try:
        # 创建引擎
        engine = create_engine(LOCAL_DATABASE_URL, echo=True)

        # 创建表
        print("📋 创建 system_configs 表...")
        SystemConfig.__table__.create(engine, checkfirst=True)

        print("📋 创建 ai_provider_configs 表...")
        AIProviderConfig.__table__.create(engine, checkfirst=True)

        print("✅ 关键配置数据表创建完成")

        # 验证表创建
        from sqlalchemy import inspect
        inspector = inspect(engine)

        tables = inspector.get_table_names()
        print(f"📊 当前数据库表: {tables}")

        if 'system_configs' in tables:
            print("✅ system_configs 表创建成功")
        else:
            print("❌ system_configs 表创建失败")

        if 'ai_provider_configs' in tables:
            print("✅ ai_provider_configs 表创建成功")
        else:
            print("❌ ai_provider_configs 表创建失败")

    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        return False

    return True

if __name__ == "__main__":
    success = create_config_tables()
    if success:
        print("\n🎉 关键配置数据表创建成功！")
        print("现在可以运行演示脚本来查看双向同步功能。")
    else:
        print("\n❌ 关键配置数据表创建失败！")
        sys.exit(1)
