#!/usr/bin/env python3
"""
演示默认运行模式的自动检测功能
展示系统如何根据环境变量自动选择部署模式
"""

import os
import sys
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flowslide.core.deployment_mode_manager import DeploymentModeManager, get_current_deployment_mode
from flowslide.core.deployment_config_manager import DeploymentConfigManager


def show_environment_detection():
    """展示环境变量检测逻辑"""
    print("🔍 环境变量检测逻辑:")
    print("=" * 60)

    # 当前环境变量
    database_url = os.environ.get('DATABASE_URL', '')
    r2_access_key = os.environ.get('R2_ACCESS_KEY_ID', '')
    force_mode = os.environ.get('FORCE_DEPLOYMENT_MODE', '')

    print(f"DATABASE_URL: {database_url or '未设置'}")
    print(f"R2_ACCESS_KEY_ID: {'已设置' if r2_access_key else '未设置'}")
    print(f"FORCE_DEPLOYMENT_MODE: {force_mode or '未设置'}")
    print()

    # 分析检测逻辑
    has_external_db = False
    if database_url:
        if database_url.startswith("postgresql://") or database_url.startswith("mysql://"):
            has_external_db = True
            print("📊 数据库分析: 检测到外部数据库 (PostgreSQL/MySQL)")
        elif database_url.startswith("sqlite:///"):
            has_external_db = False
            print("📊 数据库分析: 检测到本地SQLite数据库")
        else:
            has_external_db = True
            print("📊 数据库分析: 未知数据库类型，默认为外部数据库")
    else:
        print("📊 数据库分析: 未配置数据库，使用默认SQLite")

    has_r2 = bool(r2_access_key)
    if has_r2:
        print("☁️ 云存储分析: 检测到R2配置")
    else:
        print("☁️ 云存储分析: 未配置R2")

    # 强制模式检查
    if force_mode:
        print(f"🎯 强制模式: {force_mode}")
    else:
        print("🎯 模式选择: 自动检测")

    print()


def demonstrate_mode_detection():
    """演示模式检测功能"""
    print("🚀 模式检测演示:")
    print("=" * 60)

    # 创建模式管理器实例
    mode_manager = DeploymentModeManager()

    # 检测当前模式
    current_mode = mode_manager.detect_current_mode()
    mode_info = mode_manager.get_current_mode_info()

    print(f"🎯 检测到的模式: {current_mode.value}")
    print(f"📝 模式信息:")
    print(f"   - 当前模式: {mode_info['current_mode']}")
    print(f"   - 外部数据库: {'是' if mode_info.get('has_external_db', False) else '否'}")
    print(f"   - R2云存储: {'是' if mode_info.get('has_r2', False) else '否'}")
    print(f"   - 切换进行中: {'是' if mode_info['switch_in_progress'] else '否'}")
    print(f"   - 最后检查: {mode_info['last_mode_check'] or '从未'}")
    print()


def show_mode_scenarios():
    """展示不同场景下的模式选择"""
    print("📋 不同场景的模式选择:")
    print("=" * 60)

    scenarios = [
        {
            "name": "场景1: 开发环境 (默认)",
            "description": "本地开发，无任何配置",
            "env": {},
            "expected": "local_only"
        },
        {
            "name": "场景2: 本地开发 + 云备份",
            "description": "本地SQLite + R2云存储",
            "env": {
                "DATABASE_URL": "sqlite:///./data/flowslide.db",
                "R2_ACCESS_KEY_ID": "dev_key"
            },
            "expected": "local_r2"
        },
        {
            "name": "场景3: 生产环境数据库",
            "description": "外部PostgreSQL，无云存储",
            "env": {
                "DATABASE_URL": "postgresql://user:pass@prod-db:5432/flowslide"
            },
            "expected": "local_external"
        },
        {
            "name": "场景4: 完整生产环境",
            "description": "外部数据库 + R2云存储",
            "env": {
                "DATABASE_URL": "postgresql://user:pass@prod-db:5432/flowslide",
                "R2_ACCESS_KEY_ID": "prod_key"
            },
            "expected": "local_external_r2"
        },
        {
            "name": "场景5: 强制模式覆盖",
            "description": "强制使用特定模式",
            "env": {
                "FORCE_DEPLOYMENT_MODE": "LOCAL_ONLY",
                "DATABASE_URL": "postgresql://user:pass@prod-db:5432/flowslide",
                "R2_ACCESS_KEY_ID": "prod_key"
            },
            "expected": "local_only"
        }
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"描述: {scenario['description']}")
        print("配置:")

        # 保存原始环境变量
        original_env = {}
        for key in ['DATABASE_URL', 'R2_ACCESS_KEY_ID', 'FORCE_DEPLOYMENT_MODE']:
            original_env[key] = os.environ.get(key)

        # 设置场景环境变量
        for key, value in scenario['env'].items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        # 重新创建管理器来测试
        test_manager = DeploymentModeManager()
        detected_mode = test_manager.detect_current_mode()

        print(f"   期望模式: {scenario['expected']}")
        print(f"   检测结果: {detected_mode.value}")
        print(f"   匹配: {'✅' if detected_mode.value == scenario['expected'] else '❌'}")

        # 恢复环境变量
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]


def show_api_endpoints():
    """展示相关的API端点"""
    print("\n🌐 相关API端点:")
    print("=" * 60)

    endpoints = [
        {
            "method": "GET",
            "path": "/api/deployment/mode",
            "description": "获取当前部署模式和详细信息",
            "example": "curl http://localhost:8000/api/deployment/mode"
        },
        {
            "method": "GET",
            "path": "/api/deployment/modes",
            "description": "获取所有可用模式和当前模式",
            "example": "curl http://localhost:8000/api/deployment/modes"
        },
        {
            "method": "POST",
            "path": "/api/deployment/validate",
            "description": "验证模式配置",
            "example": 'curl -X POST http://localhost:8000/api/deployment/validate -H "Content-Type: application/json" -d \'{"mode": "LOCAL_R2", "config": {"r2_access_key_id": "test"}}\''
        }
    ]

    for endpoint in endpoints:
        print(f"\n{endpoint['method']} {endpoint['path']}")
        print(f"描述: {endpoint['description']}")
        print(f"示例: {endpoint['example']}")


def show_startup_behavior():
    """展示启动时的行为"""
    print("\n⚡ 应用启动行为:")
    print("=" * 60)

    behaviors = [
        "1. 应用启动时自动创建DeploymentModeManager实例",
        "2. 立即调用detect_current_mode()检测当前模式",
        "3. 根据检测结果初始化相应的服务",
        "4. 如果配置了R2，启动备份服务",
        "5. 如果配置了外部数据库，启动数据同步服务",
        "6. 启动模式监控服务，每60秒检查一次配置变化",
        "7. 提供REST API接口供外部查询和控制"
    ]

    for behavior in behaviors:
        print(f"   {behavior}")

    print("\n🎯 关键特性:")
    print("   • 零配置启动：无需手动指定模式")
    print("   • 自动适应：根据环境变量动态调整")
    print("   • 实时监控：检测配置变化并自动响应")
    print("   • 安全切换：支持模式间的安全切换")


def main():
    """主函数"""
    print("🎯 FlowSlide 默认运行模式自动检测演示")
    print("=" * 60)

    # 展示环境变量检测逻辑
    show_environment_detection()

    # 演示模式检测功能
    demonstrate_mode_detection()

    # 展示不同场景
    show_mode_scenarios()

    # 展示API端点
    show_api_endpoints()

    # 展示启动行为
    show_startup_behavior()

    print("\n" + "=" * 60)
    print("✨ 总结:")
    print("   FlowSlide会根据DATABASE_URL和R2_ACCESS_KEY_ID环境变量")
    print("   自动检测并选择最合适的部署模式，无需手动配置！")
    print("=" * 60)


if __name__ == "__main__":
    main()
