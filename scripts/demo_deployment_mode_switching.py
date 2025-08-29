#!/usr/bin/env python3
"""
部署模式切换演示脚本
展示如何在不同部署模式之间切换
"""

import asyncio
import os
import sys
import json
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flowslide.core.deployment_mode_manager import DeploymentModeManager
from flowslide.core.deployment_config_manager import DeploymentConfigManager


class DeploymentModeDemo:
    """部署模式切换演示类"""

    def __init__(self):
        self.mode_manager = DeploymentModeManager()
        self.config_manager = DeploymentConfigManager()

    def show_current_mode(self) -> None:
        """显示当前部署模式"""
        print("\n🔍 当前部署模式状态:")
        print("-" * 40)

        current_mode = self.mode_manager.detect_current_mode()
        print(f"检测到的模式: {current_mode}")

        # 显示环境变量状态
        db_url = os.environ.get('DATABASE_URL', '未设置')
        r2_key = os.environ.get('R2_ACCESS_KEY_ID', '未设置')

        print(f"DATABASE_URL: {db_url}")
        print(f"R2_ACCESS_KEY_ID: {'已设置' if r2_key else '未设置'}")

    def demonstrate_mode_scenarios(self) -> None:
        """演示不同模式的场景"""
        print("\n📋 部署模式场景演示:")
        print("=" * 60)

        scenarios = [
            {
                "title": "场景1: 本地开发环境 (LOCAL_ONLY)",
                "description": "仅使用本地SQLite数据库，无云存储",
                "env_vars": {
                    "DATABASE_URL": "sqlite:///./data/flowslide.db",
                    "R2_ACCESS_KEY_ID": ""
                },
                "use_case": "适合开发和测试环境"
            },
            {
                "title": "场景2: 生产环境数据库 (LOCAL_EXTERNAL)",
                "description": "使用外部PostgreSQL数据库，无云存储",
                "env_vars": {
                    "DATABASE_URL": "postgresql://user:pass@prod-db:5432/flowslide",
                    "R2_ACCESS_KEY_ID": ""
                },
                "use_case": "适合生产环境使用外部数据库"
            },
            {
                "title": "场景3: 本地开发+云备份 (LOCAL_R2)",
                "description": "本地SQLite数据库 + Cloudflare R2云存储",
                "env_vars": {
                    "DATABASE_URL": "sqlite:///./data/flowslide.db",
                    "R2_ACCESS_KEY_ID": "your_r2_access_key"
                },
                "use_case": "开发环境但需要云备份"
            },
            {
                "title": "场景4: 完整生产环境 (LOCAL_EXTERNAL_R2)",
                "description": "外部PostgreSQL数据库 + Cloudflare R2云存储",
                "env_vars": {
                    "DATABASE_URL": "postgresql://user:pass@prod-db:5432/flowslide",
                    "R2_ACCESS_KEY_ID": "your_r2_access_key"
                },
                "use_case": "完整的生产环境配置"
            }
        ]

        for scenario in scenarios:
            print(f"\n{scenario['title']}")
            print(f"描述: {scenario['description']}")
            print(f"用途: {scenario['use_case']}")
            print("配置:")

            for key, value in scenario['env_vars'].items():
                masked_value = value[:20] + "..." if len(value) > 20 else value
                print(f"  {key}: {masked_value}")

            # 模拟模式检测
            original_env = {}
            for key, value in scenario['env_vars'].items():
                original_env[key] = os.environ.get(key)
                if value:
                    os.environ[key] = value
                elif key in os.environ:
                    del os.environ[key]

            try:
                detected_mode = self.mode_manager.detect_current_mode()
                print(f"检测结果: {detected_mode}")
            finally:
                # 恢复环境变量
                for key, value in original_env.items():
                    if value is not None:
                        os.environ[key] = value
                    elif key in os.environ:
                        del os.environ[key]

    def show_transition_workflow(self) -> None:
        """展示模式切换工作流程"""
        print("\n🔄 模式切换工作流程:")
        print("=" * 60)

        workflow = [
            {
                "step": 1,
                "action": "环境变量配置",
                "description": "设置DATABASE_URL和R2_ACCESS_KEY_ID环境变量",
                "command": "export DATABASE_URL='postgresql://...' && export R2_ACCESS_KEY_ID='...'"
            },
            {
                "step": 2,
                "action": "模式检测",
                "description": "系统自动检测当前部署模式",
                "command": "curl http://localhost:8000/api/deployment/mode"
            },
            {
                "step": 3,
                "action": "配置验证",
                "description": "验证新模式的配置是否有效",
                "command": "curl http://localhost:8000/api/deployment/validate"
            },
            {
                "step": 4,
                "action": "安全切换",
                "description": "执行模式切换，包含数据迁移和清理",
                "command": "curl -X POST http://localhost:8000/api/deployment/switch"
            },
            {
                "step": 5,
                "action": "状态确认",
                "description": "确认切换成功，服务正常运行",
                "command": "curl http://localhost:8000/health"
            }
        ]

        for step_info in workflow:
            print(f"\n步骤 {step_info['step']}: {step_info['action']}")
            print(f"描述: {step_info['description']}")
            print(f"命令: {step_info['command']}")

    def show_api_endpoints(self) -> None:
        """展示可用的API端点"""
        print("\n🌐 部署模式管理API端点:")
        print("=" * 60)

        endpoints = [
            {
                "method": "GET",
                "path": "/api/deployment/mode",
                "description": "获取当前部署模式",
                "response": '{"mode": "LOCAL_EXTERNAL_R2", "status": "active"}'
            },
            {
                "method": "GET",
                "path": "/api/deployment/config",
                "description": "获取当前模式配置",
                "response": '{"database_url": "...", "r2_enabled": true, ...}'
            },
            {
                "method": "POST",
                "path": "/api/deployment/validate",
                "description": "验证模式配置",
                "request": '{"mode": "LOCAL_R2", "config": {...}}',
                "response": '{"valid": true, "warnings": []}'
            },
            {
                "method": "POST",
                "path": "/api/deployment/switch",
                "description": "切换部署模式",
                "request": '{"target_mode": "LOCAL_EXTERNAL_R2", "config": {...}}',
                "response": '{"success": true, "message": "Mode switched successfully"}'
            },
            {
                "method": "GET",
                "path": "/api/deployment/status",
                "description": "获取系统状态",
                "response": '{"mode": "LOCAL_R2", "healthy": true, "last_sync": "..."}'
            }
        ]

        for endpoint in endpoints:
            print(f"\n{endpoint['method']} {endpoint['path']}")
            print(f"描述: {endpoint['description']}")
            if 'request' in endpoint:
                print(f"请求: {endpoint['request']}")
            print(f"响应: {endpoint['response']}")

    def show_configuration_examples(self) -> None:
        """展示配置示例"""
        print("\n⚙️ 配置示例:")
        print("=" * 60)

        configs = {
            "LOCAL_ONLY": {
                "DATABASE_URL": "sqlite:///./data/flowslide.db",
                "R2_ACCESS_KEY_ID": "",
                "R2_SECRET_ACCESS_KEY": "",
                "R2_ACCOUNT_ID": ""
            },
            "LOCAL_EXTERNAL": {
                "DATABASE_URL": "postgresql://username:password@localhost:5432/flowslide",
                "R2_ACCESS_KEY_ID": "",
                "R2_SECRET_ACCESS_KEY": "",
                "R2_ACCOUNT_ID": ""
            },
            "LOCAL_R2": {
                "DATABASE_URL": "sqlite:///./data/flowslide.db",
                "R2_ACCESS_KEY_ID": "your_access_key_here",
                "R2_SECRET_ACCESS_KEY": "your_secret_key_here",
                "R2_ACCOUNT_ID": "your_account_id_here"
            },
            "LOCAL_EXTERNAL_R2": {
                "DATABASE_URL": "postgresql://username:password@prod-db:5432/flowslide",
                "R2_ACCESS_KEY_ID": "your_access_key_here",
                "R2_SECRET_ACCESS_KEY": "your_secret_key_here",
                "R2_ACCOUNT_ID": "your_account_id_here"
            }
        }

        for mode, config in configs.items():
            print(f"\n{mode} 模式配置:")
            for key, value in config.items():
                if value:
                    masked_value = value[:10] + "..." if len(value) > 10 else value
                    print(f"  {key}={masked_value}")
                else:
                    print(f"  {key}=")

    def show_monitoring_features(self) -> None:
        """展示监控功能"""
        print("\n📊 监控和维护功能:")
        print("=" * 60)

        features = [
            {
                "feature": "自动模式检测",
                "description": "系统启动时自动检测当前部署模式",
                "benefit": "无需手动配置，减少错误"
            },
            {
                "feature": "配置验证",
                "description": "切换前验证配置的完整性和正确性",
                "benefit": "防止因配置错误导致的服务中断"
            },
            {
                "feature": "数据迁移",
                "description": "模式切换时自动处理数据迁移",
                "benefit": "确保数据一致性"
            },
            {
                "feature": "健康检查",
                "description": "实时监控系统和服务的健康状态",
                "benefit": "及时发现和解决问题"
            },
            {
                "feature": "日志记录",
                "description": "详细记录模式切换过程和错误信息",
                "benefit": "便于故障排查和审计"
            },
            {
                "feature": "回滚机制",
                "description": "切换失败时自动回滚到之前的状态",
                "benefit": "保证系统稳定性"
            }
        ]

        for feature in features:
            print(f"\n🔧 {feature['feature']}")
            print(f"描述: {feature['description']}")
            print(f"优势: {feature['benefit']}")


def main():
    """主演示函数"""
    print("🚀 FlowSlide 部署模式切换系统演示")
    print("=" * 60)

    demo = DeploymentModeDemo()

    # 显示当前状态
    demo.show_current_mode()

    # 演示不同场景
    demo.demonstrate_mode_scenarios()

    # 展示切换工作流程
    demo.show_transition_workflow()

    # 展示API端点
    demo.show_api_endpoints()

    # 展示配置示例
    demo.show_configuration_examples()

    # 展示监控功能
    demo.show_monitoring_features()

    print("\n" + "=" * 60)
    print("✨ 演示完成!")
    print("您现在可以使用上述API端点来管理部署模式切换")
    print("有关详细文档，请查看项目文档或访问 /docs 端点")


if __name__ == "__main__":
    main()
