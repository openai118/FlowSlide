"""
数据同步策略配置
定义不同部署场景下的数据同步策略
"""

import os
from typing import Dict, Any, List
from enum import Enum


class DeploymentMode(Enum):
    """部署模式"""
    LOCAL_ONLY = "local_only"                    # 1. 只有本地
    LOCAL_EXTERNAL = "local_external"           # 2. 本地+外部数据库
    LOCAL_R2 = "local_r2"                       # 3. 本地+R2
    LOCAL_EXTERNAL_R2 = "local_external_r2"     # 4. 本地+外部数据库+R2


class DataSyncStrategy:
    """数据同步策略配置"""

    def __init__(self):
        self.deployment_mode = self._detect_deployment_mode()
        self.sync_strategies = self._load_sync_strategies()

    def _detect_deployment_mode(self) -> DeploymentMode:
        """检测当前部署模式"""
        has_external_db = bool(os.getenv("DATABASE_URL"))
        has_r2 = bool(os.getenv("R2_ACCESS_KEY_ID"))

        if has_external_db and has_r2:
            return DeploymentMode.LOCAL_EXTERNAL_R2
        elif has_external_db:
            return DeploymentMode.LOCAL_EXTERNAL
        elif has_r2:
            return DeploymentMode.LOCAL_R2
        else:
            return DeploymentMode.LOCAL_ONLY

    def _load_sync_strategies(self) -> Dict[str, Any]:
        """根据部署模式加载同步策略"""
        base_strategies = {
            "users": {
                "sync_enabled": True,
                "directions": ["local_to_external", "external_to_local"],
                "interval_seconds": 300,  # 5分钟 - 减少R2访问频率
                "batch_size": 50,
                "strategy": "full_duplex",
                "startup_sync": True,  # 启动时同步
                "cost_optimized": True  # 成本优化模式
            },
            "system_configs": {
                "sync_enabled": True,
                "directions": ["local_to_external", "external_to_local"],
                "interval_seconds": 600,  # 10分钟 - 关键配置减少访问频率
                "batch_size": 100,
                "strategy": "full_duplex",
                "startup_sync": True,  # 启动时同步
                "cost_optimized": True  # 成本优化模式
            },
            "ai_provider_configs": {
                "sync_enabled": True,
                "directions": ["local_to_external", "external_to_local"],
                "interval_seconds": 600,  # 10分钟 - AI配置减少访问频率
                "batch_size": 50,
                "strategy": "full_duplex",
                "startup_sync": True,  # 启动时同步
                "cost_optimized": True  # 成本优化模式
            },
            "projects": {
                "sync_enabled": True,
                "directions": ["local_to_external", "external_to_local"],
                "interval_seconds": 300,  # 5分钟
                "batch_size": 20,
                "strategy": "full_duplex"
            },
            "todo_data": {
                "sync_enabled": True,
                "directions": ["local_to_external", "external_to_local"],
                "interval_seconds": 300,  # 5分钟
                "batch_size": 30,
                "strategy": "full_duplex"
            },
            "slide_data": {
                "sync_enabled": True,
                "directions": ["local_to_external"],  # 主要从本地同步到外部
                "interval_seconds": 1800,  # 30分钟
                "batch_size": 10,
                "strategy": "on_demand"
            },
            "ppt_templates": {
                "sync_enabled": True,
                "directions": ["local_to_external", "external_to_local"],
                "interval_seconds": 1800,  # 30分钟
                "batch_size": 15,
                "strategy": "master_slave"
            },
            "global_templates": {
                "sync_enabled": True,
                "directions": ["local_to_external", "external_to_local"],
                "interval_seconds": 3600,  # 1小时
                "batch_size": 10,
                "strategy": "master_slave"
            },
            "project_versions": {
                "sync_enabled": True,
                "directions": ["local_to_external"],  # 主要备份到外部
                "interval_seconds": 3600,  # 1小时
                "batch_size": 5,
                "strategy": "backup_only"
            },
            "user_sessions": {
                "sync_enabled": False,
                "directions": [],
                "interval_seconds": 0,
                "batch_size": 0,
                "strategy": "local_only"
            }
        }

        # 根据部署模式调整策略
        return self._adjust_strategies_for_mode(base_strategies)

    def _adjust_strategies_for_mode(self, strategies: Dict[str, Any]) -> Dict[str, Any]:
        """根据部署模式调整同步策略"""

        if self.deployment_mode == DeploymentMode.LOCAL_ONLY:
            # 模式1：只有本地 - 所有数据仅本地存储
            for data_type in strategies:
                strategies[data_type].update({
                    "sync_enabled": False,
                    "directions": [],
                    "strategy": "local_only"
                })

        elif self.deployment_mode == DeploymentMode.LOCAL_EXTERNAL:
            # 模式2：本地+外部数据库 - 智能双向同步
            # 保持默认策略，但优化性能
            strategies["slide_data"]["interval_seconds"] = 900  # 15分钟
            strategies["ppt_templates"]["interval_seconds"] = 900  # 15分钟
            strategies["global_templates"]["interval_seconds"] = 1800  # 30分钟

        elif self.deployment_mode == DeploymentMode.LOCAL_R2:
            # 模式3：本地+R2 - 重点备份重要数据到云端，成本优化
            for data_type in strategies:
                if data_type in ["users", "system_configs", "ai_provider_configs"]:
                    # 关键数据保持双向同步，但优化成本
                    strategies[data_type].update({
                        "directions": ["local_to_external", "external_to_local"],
                        "interval_seconds": 3600,  # 1小时 - 大幅减少R2访问 (原来30分钟)
                        "strategy": "full_duplex",
                        "startup_sync": True,  # 启动时从R2全量同步
                        "cost_optimized": True,  # 启用成本优化
                        "sync_on_change": True  # 仅在数据变化时同步
                    })
                elif data_type in ["projects", "todo_data"]:
                    # 核心数据定期备份到R2，减少频率
                    strategies[data_type].update({
                        "directions": ["local_to_external"],  # 只上传到R2
                        "interval_seconds": 7200,  # 2小时 - 减少备份频率 (原来1小时)
                        "strategy": "backup_only",
                        "startup_sync": False,  # 启动时不从R2同步
                        "cost_optimized": True,
                        "sync_on_change": False  # 定期备份，不关心变化
                    })
                else:
                    # 其他数据按需备份，最大限度减少R2访问
                    strategies[data_type].update({
                        "directions": ["local_to_external"],
                        "interval_seconds": 14400,  # 4小时 - 进一步减少访问 (原来2小时)
                        "strategy": "backup_only",
                        "startup_sync": False,
                        "cost_optimized": True,
                        "sync_on_change": False
                    })

        elif self.deployment_mode == DeploymentMode.LOCAL_EXTERNAL_R2:
            # 模式4：本地+外部数据库+R2 - 三层架构，最大化可靠性，成本优化
            # 关键数据：本地↔外部数据库双向同步，R2定期备份
            for data_type in ["users", "system_configs", "ai_provider_configs"]:
                strategies[data_type].update({
                    "directions": ["local_to_external", "external_to_local"],  # 本地↔外部数据库双向
                    "interval_seconds": 600,  # 10分钟 - 快速双向同步
                    "strategy": "full_duplex",
                    "startup_sync": True,
                    "cost_optimized": True,
                    "sync_on_change": True,
                    "r2_backup_only": True,  # R2只做备份，不参与双向同步
                    "r2_backup_interval": 7200,  # R2备份间隔2小时
                    "r2_primary": False,  # 外部数据库是主要存储
                    "external_sync_interval": 600  # 外部同步间隔10分钟
                })

            # 核心业务数据：本地↔外部数据库双向同步，R2定期备份
            for data_type in ["projects", "todo_data"]:
                strategies[data_type].update({
                    "directions": ["local_to_external", "external_to_local"],  # 本地↔外部数据库双向
                    "interval_seconds": 900,  # 15分钟 - 业务数据同步
                    "strategy": "full_duplex",
                    "startup_sync": True,
                    "cost_optimized": True,
                    "sync_on_change": True,
                    "r2_backup_only": True,  # R2只做备份
                    "r2_backup_interval": 3600,  # R2备份间隔1小时
                    "r2_primary": False,  # 外部数据库是主要存储
                    "external_sync_interval": 900  # 外部同步间隔15分钟
                })

            # 大数据内容：主要备份到R2，外部数据库按需同步
            strategies["slide_data"].update({
                "directions": ["local_to_external"],  # 主要备份到R2
                "interval_seconds": 14400,  # 4小时 - R2备份间隔
                "strategy": "backup_only",  # R2备份策略
                "startup_sync": False,
                "cost_optimized": True,
                "sync_on_change": False,
                "r2_primary": True,  # R2是主要存储
                "r2_backup_only": False,  # R2是主要存储，不是只备份
                "r2_backup_interval": 14400,  # R2同步间隔4小时
                "external_sync_interval": 28800  # 外部数据库同步间隔8小时
            })

            # 模板数据：R2主要存储，外部数据库定期同步
            for data_type in ["ppt_templates", "global_templates"]:
                strategies[data_type].update({
                    "directions": ["local_to_external"],  # 主要备份到R2
                    "interval_seconds": 10800,  # 3小时 - R2备份间隔
                    "strategy": "backup_only",  # R2备份策略
                    "startup_sync": False,
                    "cost_optimized": True,
                    "sync_on_change": False,
                    "r2_primary": True,  # R2是主要存储
                    "r2_backup_only": False,  # R2是主要存储，不是只备份
                    "r2_backup_interval": 10800,  # R2同步间隔3小时
                    "external_sync_interval": 21600  # 外部数据库同步间隔6小时
                })

        return strategies

    def get_strategy_for_data_type(self, data_type: str) -> Dict[str, Any]:
        """获取特定数据类型的同步策略"""
        return self.sync_strategies.get(data_type, {
            "sync_enabled": False,
            "directions": [],
            "interval_seconds": 0,
            "batch_size": 0,
            "strategy": "local_only"
        })

    def get_all_strategies(self) -> Dict[str, Any]:
        """获取所有同步策略"""
        return self.sync_strategies

    def is_sync_enabled_for_type(self, data_type: str) -> bool:
        """检查特定数据类型是否启用同步"""
        strategy = self.get_strategy_for_data_type(data_type)
        return strategy["sync_enabled"]

    def get_sync_directions_for_type(self, data_type: str) -> List[str]:
        """获取特定数据类型的同步方向"""
        strategy = self.get_strategy_for_data_type(data_type)
        return strategy["directions"]

    def get_sync_interval_for_type(self, data_type: str) -> int:
        """获取特定数据类型的同步间隔"""
        strategy = self.get_strategy_for_data_type(data_type)
        return strategy["interval_seconds"]

    def get_batch_size_for_type(self, data_type: str) -> int:
        """获取特定数据类型的批处理大小"""
        strategy = self.get_strategy_for_data_type(data_type)
        return strategy["batch_size"]

    def should_startup_sync_for_type(self, data_type: str) -> bool:
        """检查特定数据类型是否需要在启动时同步"""
        strategy = self.get_strategy_for_data_type(data_type)
        return strategy.get("startup_sync", False)

    def is_cost_optimized_for_type(self, data_type: str) -> bool:
        """检查特定数据类型是否启用成本优化"""
        strategy = self.get_strategy_for_data_type(data_type)
        return strategy.get("cost_optimized", False)

    def should_sync_on_change_for_type(self, data_type: str) -> bool:
        """检查特定数据类型是否只在变化时同步"""
        strategy = self.get_strategy_for_data_type(data_type)
        return strategy.get("sync_on_change", False)

    def get_startup_sync_types(self) -> List[str]:
        """获取需要在启动时同步的数据类型"""
        return [data_type for data_type in self.sync_strategies
                if self.should_startup_sync_for_type(data_type)]

    def get_cost_optimized_types(self) -> List[str]:
        """获取启用成本优化的数据类型"""
        return [data_type for data_type in self.sync_strategies
                if self.is_cost_optimized_for_type(data_type)]

    def get_sync_on_change_types(self) -> List[str]:
        """获取只在变化时同步的数据类型"""
        return [data_type for data_type in self.sync_strategies
                if self.should_sync_on_change_for_type(data_type)]

    def get_deployment_info(self) -> Dict[str, Any]:
        """获取部署模式信息"""
        return {
            "deployment_mode": self.deployment_mode.value,
            "has_external_db": bool(os.getenv("DATABASE_URL")),
            "has_r2": bool(os.getenv("R2_ACCESS_KEY_ID")),
            "local_db_type": "sqlite",
            "external_db_url": bool(os.getenv("DATABASE_URL")),
            "r2_endpoint": bool(os.getenv("R2_ENDPOINT")),
            "r2_bucket": os.getenv("R2_BUCKET_NAME")
        }


# 创建全局策略配置实例
sync_strategy_config = DataSyncStrategy()


def get_sync_strategy_for_type(data_type: str) -> Dict[str, Any]:
    """获取数据类型同步策略的便捷函数"""
    return sync_strategy_config.get_strategy_for_data_type(data_type)


def is_sync_enabled_for_type(data_type: str) -> bool:
    """检查数据类型同步是否启用的便捷函数"""
    return sync_strategy_config.is_sync_enabled_for_type(data_type)


def get_deployment_mode() -> str:
    """获取当前部署模式的便捷函数"""
    return sync_strategy_config.deployment_mode.value
