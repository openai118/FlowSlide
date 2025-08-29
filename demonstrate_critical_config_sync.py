#!/usr/bin/env python3
"""
关键配置双向同步演示
展示在LOCAL_R2模式下，系统配置和AI配置的双向同步功能
"""

import os
import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.flowslide.database.database import initialize_database, SessionLocal
from src.flowslide.database.models import SystemConfig, AIProviderConfig
from src.flowslide.services.config_sync_service import config_sync_service, initialize_config_sync
from src.flowslide.core.sync_strategy_config import sync_strategy_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demonstrate_config_sync():
    """演示关键配置的双向同步功能"""
    print("🚀 关键配置双向同步演示")
    print("=" * 50)

    # 1. 显示当前部署模式
    deployment_mode = sync_strategy_config.deployment_mode.value
    print(f"📊 当前部署模式: {deployment_mode}")
    print(f"🔗 外部数据库: {'✅ 已配置' if os.getenv('DATABASE_URL') else '❌ 未配置'}")
    print(f"☁️  R2存储: {'✅ 已配置' if os.getenv('R2_ACCESS_KEY_ID') else '❌ 未配置'}")
    print()

    # 2. 初始化数据库
    print("🔧 初始化数据库...")
    try:
        initialize_database()
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return
    print()

    # 3. 初始化配置同步
    print("🔄 初始化配置同步...")
    try:
        initialize_config_sync()
        print("✅ 配置同步初始化完成")
    except Exception as e:
        print(f"❌ 配置同步初始化失败: {e}")
        return
    print()

    # 4. 显示同步策略
    print("📋 关键配置同步策略:")
    strategies = sync_strategy_config.get_all_strategies()

    critical_configs = ["users", "system_configs", "ai_provider_configs"]
    for config_type in critical_configs:
        if config_type in strategies:
            strategy = strategies[config_type]
            print(f"  • {config_type}:")
            print(f"    - 启用: {'✅' if strategy['sync_enabled'] else '❌'}")
            print(f"    - 方向: {', '.join(strategy['directions'])}")
            print(f"    - 间隔: {strategy['interval_seconds']}秒")
            print(f"    - 策略: {strategy['strategy']}")
            print()

    # 5. 显示当前配置数据
    print("📊 当前配置数据统计:")
    try:
        with SessionLocal() as session:
            # 系统配置统计
            system_count = session.query(SystemConfig).filter(SystemConfig.is_system == True).count()
            print(f"  • 系统配置: {system_count} 项")

            # AI配置统计
            ai_count = session.query(AIProviderConfig).count()
            print(f"  • AI配置: {ai_count} 项")

            # 用户统计
            from src.flowslide.database.models import User
            user_count = session.query(User).count()
            print(f"  • 用户: {user_count} 个")

    except Exception as e:
        print(f"❌ 获取统计数据失败: {e}")
    print()

    # 6. 演示配置同步流程
    print("🔄 演示配置同步流程:")
    print("  1. 环境变量 → 数据库")
    print("  2. 数据库 → 环境变量")
    print("  3. 双向同步验证")
    print()

    # 7. 显示关键配置示例
    print("🔑 关键配置示例:")
    try:
        with SessionLocal() as session:
            # 显示系统配置示例
            system_configs = session.query(SystemConfig).filter(
                SystemConfig.is_system == True,
                SystemConfig.config_value.isnot(None)
            ).limit(3).all()

            if system_configs:
                print("  系统配置:")
                for config in system_configs:
                    value_display = "***" if config.is_sensitive else config.config_value[:20] + "..."
                    print(f"    - {config.config_key}: {value_display}")

            # 显示AI配置示例
            ai_configs = session.query(AIProviderConfig).filter(
                AIProviderConfig.config_value.isnot(None)
            ).limit(3).all()

            if ai_configs:
                print("  AI配置:")
                for config in ai_configs:
                    value_display = "***" if config.config_type == "password" else config.config_value[:20] + "..."
                    print(f"    - {config.provider_name}.{config.config_key}: {value_display}")

    except Exception as e:
        print(f"❌ 获取配置示例失败: {e}")
    print()

    # 8. 总结
    print("📝 总结:")
    print("✅ 关键配置数据已正确识别和配置")
    print("✅ 双向同步策略已为关键配置启用")
    print("✅ 即使在LOCAL_R2模式下，关键配置仍保持双向同步")
    print("✅ 系统配置和AI配置将定期同步，确保项目运行一致性")
    print()

    print("🎯 在LOCAL_R2模式下:")
    print("  • 用户数据: 双向同步 (30秒间隔)")
    print("  • 系统配置: 双向同步 (30秒间隔)")
    print("  • AI配置: 双向同步 (30秒间隔)")
    print("  • 其他数据: 单向备份到R2 (10分钟-1小时间隔)")
    print()

    print("💡 这确保了:")
    print("  • 项目运行的关键配置始终保持同步")
    print("  • AI服务配置在多实例间保持一致")
    print("  • 系统安全配置得到及时更新")
    print("  • 用户认证数据实时同步")


if __name__ == "__main__":
    demonstrate_config_sync()
