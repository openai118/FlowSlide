"""
智能数据同步服务 - 分层同步策略
根据数据类型、访问频率和重要性实现差异化同步
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import db_manager
from ..database.models import User, Project, PPTTemplate, GlobalMasterTemplate, TodoBoard, TodoStage, ProjectVersion, SlideData, UserSession, SystemConfig, AIProviderConfig

logger = logging.getLogger(__name__)


class SyncPriority(Enum):
    """同步优先级"""
    CRITICAL = "critical"      # 关键数据 - 必须立即同步
    HIGH = "high"             # 高优先级 - 定期同步
    MEDIUM = "medium"         # 中等优先级 - 按需同步
    LOW = "low"               # 低优先级 - 延迟同步
    LOCAL_ONLY = "local_only" # 仅本地 - 不同步


class SyncStrategy(Enum):
    """同步策略"""
    FULL_DUPLEX = "full_duplex"        # 全双向同步
    MASTER_SLAVE = "master_slave"      # 主从同步
    ON_DEMAND = "on_demand"           # 按需同步
    BACKUP_ONLY = "backup_only"       # 仅备份
    LOCAL_ONLY = "local_only"         # 仅本地


class DataSyncManager:
    """智能数据同步管理器"""

    def __init__(self):
        # 成本优化：大幅增加同步间隔，减少R2访问
        self.sync_interval = int(os.getenv("SYNC_INTERVAL", "1800"))  # 默认30分钟 (原来10分钟)
        self.fast_sync_interval = int(os.getenv("FAST_SYNC_INTERVAL", "900"))  # 快速同步15分钟 (原来5分钟)
        self.slow_sync_interval = int(os.getenv("SLOW_SYNC_INTERVAL", "14400"))  # 慢速同步4小时 (原来2小时)

        self.last_sync_time = None
        self.last_fast_sync = None
        self.last_slow_sync = None
        self.is_running = False

        # 数据同步策略配置
        self.data_sync_strategies = self._define_sync_strategies()
        self.sync_directions = self._determine_sync_directions()

        # 缓存和状态管理
        self.recently_accessed_projects: Set[str] = set()
        self.hot_data_cache: Dict[str, datetime] = {}

        # 成本优化：跟踪数据变化，避免不必要的同步
        self.data_change_tracker: Dict[str, datetime] = {}
        self.last_successful_sync: Dict[str, datetime] = {}

    def _define_sync_strategies(self) -> Dict[str, Dict[str, Any]]:
        """定义各类数据的同步策略"""
        from ..core.sync_strategy_config import sync_strategy_config

        # 获取配置的同步策略
        config_strategies = sync_strategy_config.get_all_strategies()

        strategies = {
            # 用户数据 - 关键数据，必须实时同步
            "users": {
                "priority": SyncPriority.CRITICAL,
                "strategy": SyncStrategy.FULL_DUPLEX,
                "sync_interval": self.fast_sync_interval,
                "batch_size": 50,
                "enable_deletion_sync": True,
                "description": "用户认证和权限数据，实时双向同步",
                "r2_backup_only": config_strategies.get("users", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("users", {}).get("r2_backup_interval", 7200),
                "r2_primary": config_strategies.get("users", {}).get("r2_primary", False),
                "external_sync_interval": config_strategies.get("users", {}).get("external_sync_interval", 600)
            },

            # 系统配置 - 关键数据，必须实时同步
            "system_configs": {
                "priority": SyncPriority.CRITICAL,
                "strategy": SyncStrategy.FULL_DUPLEX,
                "sync_interval": self.fast_sync_interval,
                "batch_size": 100,
                "enable_deletion_sync": True,
                "description": "系统配置参数，实时双向同步",
                "r2_backup_only": config_strategies.get("system_configs", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("system_configs", {}).get("r2_backup_interval", 7200),
                "r2_primary": config_strategies.get("system_configs", {}).get("r2_primary", False),
                "external_sync_interval": config_strategies.get("system_configs", {}).get("external_sync_interval", 600)
            },

            # AI提供商配置 - 关键数据，必须实时同步
            "ai_provider_configs": {
                "priority": SyncPriority.CRITICAL,
                "strategy": SyncStrategy.FULL_DUPLEX,
                "sync_interval": self.fast_sync_interval,
                "batch_size": 50,
                "enable_deletion_sync": True,
                "description": "AI提供商配置参数，实时双向同步",
                "r2_backup_only": config_strategies.get("ai_provider_configs", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("ai_provider_configs", {}).get("r2_backup_interval", 7200),
                "r2_primary": config_strategies.get("ai_provider_configs", {}).get("r2_primary", False),
                "external_sync_interval": config_strategies.get("ai_provider_configs", {}).get("external_sync_interval", 600)
            },

            # 项目基本信息 - 高优先级，定期同步
            "projects": {
                "priority": SyncPriority.HIGH,
                "strategy": SyncStrategy.FULL_DUPLEX,
                "sync_interval": self.sync_interval,
                "batch_size": 20,
                "enable_deletion_sync": True,
                "description": "项目基本信息和元数据，双向同步",
                "r2_backup_only": config_strategies.get("projects", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("projects", {}).get("r2_backup_interval", 3600),
                "r2_primary": config_strategies.get("projects", {}).get("r2_primary", False),
                "external_sync_interval": config_strategies.get("projects", {}).get("external_sync_interval", 900)
            },

            # 幻灯片数据 - 中等优先级，按需同步
            "slide_data": {
                "priority": SyncPriority.MEDIUM,
                "strategy": SyncStrategy.ON_DEMAND,
                "sync_interval": self.slow_sync_interval,
                "batch_size": 10,
                "enable_deletion_sync": False,
                "description": "幻灯片详细内容，按需同步活跃项目",
                "r2_backup_only": config_strategies.get("slide_data", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("slide_data", {}).get("r2_backup_interval", 14400),
                "r2_primary": config_strategies.get("slide_data", {}).get("r2_primary", True),
                "external_sync_interval": config_strategies.get("slide_data", {}).get("external_sync_interval", 28800)
            },

            # 项目版本 - 中等优先级，定期备份
            "project_versions": {
                "priority": SyncPriority.MEDIUM,
                "strategy": SyncStrategy.MASTER_SLAVE,
                "sync_interval": self.slow_sync_interval,
                "batch_size": 5,
                "enable_deletion_sync": False,
                "description": "版本历史记录，主从同步",
                "r2_backup_only": config_strategies.get("project_versions", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("project_versions", {}).get("r2_backup_interval", 7200),
                "r2_primary": config_strategies.get("project_versions", {}).get("r2_primary", False),
                "external_sync_interval": config_strategies.get("project_versions", {}).get("external_sync_interval", 14400)
            },

            # TODO工作流 - 高优先级，定期同步
            "todo_data": {
                "priority": SyncPriority.HIGH,
                "strategy": SyncStrategy.FULL_DUPLEX,
                "sync_interval": self.sync_interval,
                "batch_size": 30,
                "enable_deletion_sync": True,
                "description": "项目工作流数据，双向同步",
                "r2_backup_only": config_strategies.get("todo_data", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("todo_data", {}).get("r2_backup_interval", 3600),
                "r2_primary": config_strategies.get("todo_data", {}).get("r2_primary", False),
                "external_sync_interval": config_strategies.get("todo_data", {}).get("external_sync_interval", 900)
            },

            # 项目特定模板 - 中等优先级，按需同步
            "ppt_templates": {
                "priority": SyncPriority.MEDIUM,
                "strategy": SyncStrategy.ON_DEMAND,
                "sync_interval": self.slow_sync_interval,
                "batch_size": 15,
                "enable_deletion_sync": False,
                "description": "项目特定模板，按需同步",
                "r2_backup_only": config_strategies.get("ppt_templates", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("ppt_templates", {}).get("r2_backup_interval", 10800),
                "r2_primary": config_strategies.get("ppt_templates", {}).get("r2_primary", True),
                "external_sync_interval": config_strategies.get("ppt_templates", {}).get("external_sync_interval", 21600)
            },

            # 全局模板 - 低优先级，定期同步
            "global_templates": {
                "priority": SyncPriority.LOW,
                "strategy": SyncStrategy.MASTER_SLAVE,
                "sync_interval": self.slow_sync_interval,
                "batch_size": 10,
                "enable_deletion_sync": False,
                "description": "全局母版模板，主从同步",
                "r2_backup_only": config_strategies.get("global_templates", {}).get("r2_backup_only", False),
                "r2_backup_interval": config_strategies.get("global_templates", {}).get("r2_backup_interval", 10800),
                "r2_primary": config_strategies.get("global_templates", {}).get("r2_primary", True),
                "external_sync_interval": config_strategies.get("global_templates", {}).get("external_sync_interval", 21600)
            },

            # 用户会话 - 仅本地，不同步
            "user_sessions": {
                "priority": SyncPriority.LOCAL_ONLY,
                "strategy": SyncStrategy.LOCAL_ONLY,
                "sync_interval": 0,
                "batch_size": 0,
                "enable_deletion_sync": False,
                "description": "临时会话数据，仅保存在本地",
                "r2_backup_only": False,
                "r2_backup_interval": 0,
                "r2_primary": False,
                "external_sync_interval": 0
            }
        }

        return strategies

    def get_effective_sync_interval(self, data_type: str) -> int:
        """获取数据类型的有效同步间隔（考虑分层策略）"""
        strategy = self.data_sync_strategies.get(data_type, {})
        base_interval = strategy.get("sync_interval", self.sync_interval)

        # 检查是否有分层同步配置
        if strategy.get("r2_primary", False):
            # R2是主要存储，使用R2备份间隔
            return strategy.get("r2_backup_interval", base_interval)
        elif strategy.get("r2_backup_only", False):
            # R2只做备份，使用外部同步间隔
            return strategy.get("external_sync_interval", base_interval)

        return base_interval

    def should_sync_to_r2(self, data_type: str) -> bool:
        """判断是否应该同步到R2"""
        strategy = self.data_sync_strategies.get(data_type, {})

        # 如果R2是主要存储，肯定要同步
        if strategy.get("r2_primary", False):
            return True

        # 如果R2只做备份，检查是否到备份时间
        if strategy.get("r2_backup_only", False):
            last_sync = self.last_successful_sync.get(data_type)
            if last_sync:
                backup_interval = strategy.get("r2_backup_interval", 7200)
                return (datetime.now() - last_sync).total_seconds() >= backup_interval

        return False

    def should_sync_to_external(self, data_type: str) -> bool:
        """判断是否应该同步到外部数据库"""
        strategy = self.data_sync_strategies.get(data_type, {})

        # 如果R2是主要存储，外部同步间隔更长
        if strategy.get("r2_primary", False):
            last_sync = self.last_successful_sync.get(data_type)
            if last_sync:
                external_interval = strategy.get("external_sync_interval", 21600)
                return (datetime.now() - last_sync).total_seconds() >= external_interval
            return True  # 首次同步

        # 正常同步逻辑
        return True

    def get_sync_targets(self, data_type: str) -> List[str]:
        """获取数据类型的同步目标"""
        strategy = self.data_sync_strategies.get(data_type, {})
        targets = []

        # 检查外部数据库
        if db_manager.external_url and db_manager.sync_enabled:
            targets.append("external")

        # 检查R2
        if os.getenv("R2_ACCESS_KEY_ID") and self.should_sync_to_r2(data_type):
            targets.append("r2")

        return targets

    def _determine_sync_directions(self) -> List[str]:
        """根据数据库配置确定同步方向"""
        directions = []

        # 检查环境变量中的同步配置
        enable_sync = os.getenv("ENABLE_DATA_SYNC", "false").lower() == "true"
        sync_directions = os.getenv("SYNC_DIRECTIONS", "local_to_external,external_to_local")

        if db_manager.external_url:
            # 如果明确启用了同步，或者是混合模式
            if enable_sync or db_manager.sync_enabled:
                # 解析同步方向配置
                if "local_to_external" in sync_directions:
                    directions.append("local_to_external")
                if "external_to_local" in sync_directions:
                    directions.append("external_to_local")
            elif db_manager.database_type == "postgresql":
                # 纯外部模式：只从外部同步
                directions.append("external_to_local")

        logger.info(f"🔄 Sync directions determined: {directions} (enable_sync: {enable_sync}, db_sync_enabled: {db_manager.sync_enabled})")
        return directions
        """根据配置确定同步方向"""
        directions = []

        # 检查外部数据库配置
        has_external_db = bool(db_manager.external_url)
        # 检查R2配置
        has_r2 = bool(os.getenv("R2_ACCESS_KEY_ID"))

        if has_external_db:
            enable_sync = os.getenv("ENABLE_DATA_SYNC", "false").lower() == "true"
            sync_directions = os.getenv("SYNC_DIRECTIONS", "local_to_external,external_to_local")

            if enable_sync or db_manager.sync_enabled:
                if "local_to_external" in sync_directions:
                    directions.append("local_to_external")
                if "external_to_local" in sync_directions:
                    directions.append("external_to_local")
            elif db_manager.database_type == "postgresql":
                directions.append("external_to_local")

        logger.info(f"🔄 Sync directions: {directions}")
        logger.info(f"🔄 External DB: {has_external_db}, R2: {has_r2}")
        return directions

    async def start_smart_sync(self):
        """启动智能同步服务"""
        if not self.sync_directions:
            logger.info("🔄 Smart sync disabled - no external database configured")
            return

        self.is_running = True
        logger.info("🚀 Starting smart data synchronization service")
        logger.info(f"📊 Sync strategies loaded: {len(self.data_sync_strategies)} data types")

        # 首先执行启动同步 - 从R2全量同步关键数据到本地
        await self._perform_startup_sync()

        # 启动多层同步任务
        tasks = [
            self._fast_sync_loop(),      # 快速同步循环 - 关键数据
            self._regular_sync_loop(),   # 定期同步循环 - 高优先级数据
            self._slow_sync_loop(),      # 慢速同步循环 - 低优先级数据
            self._on_demand_sync_loop(), # 按需同步循环
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _perform_startup_sync(self):
        """执行启动同步 - 从R2全量同步关键数据到本地"""
        try:
            logger.info("🔄 Performing startup synchronization from R2...")

            # 获取需要启动同步的数据类型
            from ..core.sync_strategy_config import sync_strategy_config
            startup_sync_types = sync_strategy_config.get_startup_sync_types()

            if not startup_sync_types:
                logger.info("ℹ️ No data types require startup sync")
                return

            logger.info(f"📋 Startup sync for: {', '.join(startup_sync_types)}")

            # 按优先级顺序执行启动同步
            sync_tasks = []
            for data_type in startup_sync_types:
                if data_type in self.data_sync_strategies:
                    # 启动同步主要关注从外部到本地的同步
                    if "external_to_local" in self.sync_directions:
                        sync_tasks.append(self._sync_data_type_external_to_local(
                            data_type, self.data_sync_strategies[data_type]
                        ))

            if sync_tasks:
                logger.info(f"🔄 Executing {len(sync_tasks)} startup sync tasks...")
                await asyncio.gather(*sync_tasks, return_exceptions=True)
                logger.info("✅ Startup synchronization completed")
            else:
                logger.info("ℹ️ No startup sync tasks to execute")

        except Exception as e:
            logger.error(f"❌ Startup sync failed: {e}")

    async def _fast_sync_loop(self):
        """快速同步循环 - 处理关键数据"""
        while self.is_running:
            try:
                await self._sync_by_priority(SyncPriority.CRITICAL)
                await asyncio.sleep(self.fast_sync_interval)
            except Exception as e:
                logger.error(f"❌ Fast sync error: {e}")
                await asyncio.sleep(30)

    async def _regular_sync_loop(self):
        """定期同步循环 - 处理高优先级数据"""
        while self.is_running:
            try:
                await self._sync_by_priority(SyncPriority.HIGH)
                self.last_sync_time = datetime.now()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"❌ Regular sync error: {e}")
                await asyncio.sleep(60)

    async def _slow_sync_loop(self):
        """慢速同步循环 - 处理低优先级数据"""
        while self.is_running:
            try:
                await self._sync_by_priority(SyncPriority.MEDIUM)
                await self._sync_by_priority(SyncPriority.LOW)
                self.last_slow_sync = datetime.now()
                await asyncio.sleep(self.slow_sync_interval)
            except Exception as e:
                logger.error(f"❌ Slow sync error: {e}")
                await asyncio.sleep(300)

    async def _on_demand_sync_loop(self):
        """按需同步循环 - 处理需要按需同步的数据"""
        while self.is_running:
            try:
                await self._sync_on_demand_data()
                await asyncio.sleep(120)  # 每2分钟检查一次
            except Exception as e:
                logger.error(f"❌ On-demand sync error: {e}")
                await asyncio.sleep(60)

    async def _sync_by_priority(self, priority: SyncPriority):
        """按优先级同步数据"""
        sync_tasks = []

        for data_type, config in self.data_sync_strategies.items():
            if config["priority"] == priority and config["strategy"] != SyncStrategy.LOCAL_ONLY:
                if config["strategy"] == SyncStrategy.ON_DEMAND:
                    continue  # 按需同步单独处理

                for direction in self.sync_directions:
                    if direction == "local_to_external":
                        sync_tasks.append(self._sync_data_type_local_to_external(data_type, config))
                    elif direction == "external_to_local":
                        sync_tasks.append(self._sync_data_type_external_to_local(data_type, config))

        if sync_tasks:
            logger.info(f"🔄 Syncing {priority.value} priority data ({len(sync_tasks)} tasks)")
            await asyncio.gather(*sync_tasks, return_exceptions=True)

    async def _sync_on_demand_data(self):
        """同步按需数据 - 只同步最近访问的项目相关数据"""
        if not self.recently_accessed_projects:
            return

        logger.info(f"🔄 On-demand sync for {len(self.recently_accessed_projects)} projects")

        # 同步活跃项目的幻灯片数据
        for project_id in list(self.recently_accessed_projects):
            await self._sync_project_slide_data(project_id)

            # 同步活跃项目的模板数据
            await self._sync_project_template_data(project_id)

        # 清理旧的访问记录（保留最近1小时的记录）
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.recently_accessed_projects = {
            pid for pid in self.recently_accessed_projects
            if pid in self.hot_data_cache and self.hot_data_cache[pid] > cutoff_time
        }

    async def _sync_data_type_local_to_external(self, data_type: str, config: Dict[str, Any]):
        """同步特定数据类型从本地到外部"""
        try:
            strategy = config["strategy"]
            batch_size = config["batch_size"]

            if data_type == "users":
                await self._sync_users_local_to_external()
            elif data_type == "system_configs":
                await self._sync_system_configs_local_to_external()
            elif data_type == "ai_provider_configs":
                await self._sync_ai_provider_configs_local_to_external()
            elif data_type == "projects":
                await self._sync_projects_local_to_external(batch_size)
            elif data_type == "todo_data":
                await self._sync_todo_data_local_to_external(batch_size)
            elif data_type == "global_templates":
                await self._sync_global_templates_local_to_external(batch_size)
            elif data_type == "project_versions":
                await self._sync_project_versions_local_to_external(batch_size)

        except Exception as e:
            logger.error(f"❌ Failed to sync {data_type} local to external: {e}")

    async def _sync_data_type_external_to_local(self, data_type: str, config: Dict[str, Any]):
        """同步特定数据类型从外部到本地"""
        try:
            strategy = config["strategy"]
            batch_size = config["batch_size"]

            if data_type == "users":
                await self._sync_users_external_to_local()
            elif data_type == "system_configs":
                await self._sync_system_configs_external_to_local()
            elif data_type == "ai_provider_configs":
                await self._sync_ai_provider_configs_external_to_local()
            elif data_type == "projects":
                await self._sync_projects_external_to_local(batch_size)
            elif data_type == "todo_data":
                await self._sync_todo_data_external_to_local(batch_size)
            elif data_type == "global_templates":
                await self._sync_global_templates_external_to_local(batch_size)
            elif data_type == "project_versions":
                await self._sync_project_versions_external_to_local(batch_size)

        except Exception as e:
            logger.error(f"❌ Failed to sync {data_type} external to local: {e}")

    async def _sync_project_slide_data(self, project_id: str):
        """同步特定项目的幻灯片数据"""
        try:
            logger.debug(f"🔄 Syncing slide data for project {project_id}")

            # 这里实现按需幻灯片同步逻辑
            # 只同步最近修改的幻灯片数据

        except Exception as e:
            logger.error(f"❌ Failed to sync slide data for project {project_id}: {e}")

    async def _sync_project_template_data(self, project_id: str):
        """同步特定项目的模板数据"""
        try:
            logger.debug(f"🔄 Syncing template data for project {project_id}")

            # 这里实现按需模板同步逻辑

        except Exception as e:
            logger.error(f"❌ Failed to sync template data for project {project_id}: {e}")

    # 基础同步方法实现（保留原有逻辑，但按数据类型分离）
    async def _sync_users_local_to_external(self):
        """智能同步本地用户到外部数据库"""
        # 实现用户同步逻辑（复用原有实现）
        pass

    async def _sync_users_external_to_local(self):
        """智能同步外部用户到本地数据库"""
        # 实现用户同步逻辑（复用原有实现）
        pass

    async def _sync_system_configs_local_to_external(self):
        """同步本地系统配置到外部数据库"""
        try:
            logger.info("🔄 Syncing system configs from local to external database")
            # 使用配置同步服务进行同步
            from .config_sync_service import config_sync_service

            # 这里可以实现更复杂的双向同步逻辑
            # 目前先记录日志，后续实现具体同步逻辑
            logger.info("✅ System configs sync placeholder - implementation needed")

        except Exception as e:
            logger.error(f"❌ Failed to sync system configs local to external: {e}")

    async def _sync_system_configs_external_to_local(self):
        """同步外部系统配置到本地数据库"""
        try:
            logger.info("🔄 Syncing system configs from external to local database")
            # 使用配置同步服务进行同步
            from .config_sync_service import config_sync_service

            # 这里可以实现更复杂的双向同步逻辑
            logger.info("✅ System configs sync placeholder - implementation needed")

        except Exception as e:
            logger.error(f"❌ Failed to sync system configs external to local: {e}")

    async def _sync_ai_provider_configs_local_to_external(self):
        """同步本地AI提供商配置到外部数据库"""
        try:
            logger.info("🔄 Syncing AI provider configs from local to external database")
            # 使用配置同步服务进行同步
            from .config_sync_service import config_sync_service

            # 这里可以实现更复杂的双向同步逻辑
            logger.info("✅ AI provider configs sync placeholder - implementation needed")

        except Exception as e:
            logger.error(f"❌ Failed to sync AI provider configs local to external: {e}")

    async def _sync_ai_provider_configs_external_to_local(self):
        """同步外部AI提供商配置到本地数据库"""
        try:
            logger.info("🔄 Syncing AI provider configs from external to local database")
            # 使用配置同步服务进行同步
            from .config_sync_service import config_sync_service

            # 这里可以实现更复杂的双向同步逻辑
            logger.info("✅ AI provider configs sync placeholder - implementation needed")

        except Exception as e:
            logger.error(f"❌ Failed to sync AI provider configs external to local: {e}")

    async def _sync_projects_local_to_external(self, batch_size: int):
        """批量同步本地项目到外部数据库"""
        # 实现项目同步逻辑
        pass

    async def _sync_projects_external_to_local(self, batch_size: int):
        """批量同步外部项目到本地数据库"""
        # 实现项目同步逻辑
        pass

    async def _sync_todo_data_local_to_external(self, batch_size: int):
        """同步本地TODO数据到外部数据库"""
        # 实现TODO同步逻辑
        pass

    async def _sync_todo_data_external_to_local(self, batch_size: int):
        """同步外部TODO数据到本地数据库"""
        # 实现TODO同步逻辑
        pass

    async def _sync_global_templates_local_to_external(self, batch_size: int):
        """同步本地全局模板到外部数据库"""
        # 实现全局模板同步逻辑
        pass

    async def _sync_global_templates_external_to_local(self, batch_size: int):
        """同步外部全局模板到本地数据库"""
        # 实现全局模板同步逻辑
        pass

    async def _sync_project_versions_local_to_external(self, batch_size: int):
        """同步本地项目版本到外部数据库"""
        # 实现项目版本同步逻辑
        pass

    async def _sync_project_versions_external_to_local(self, batch_size: int):
        """同步外部项目版本到本地数据库"""
        # 实现项目版本同步逻辑
        pass

    def mark_project_accessed(self, project_id: str):
        """标记项目被访问，用于按需同步"""
        self.recently_accessed_projects.add(project_id)
        self.hot_data_cache[project_id] = datetime.now()

    async def get_sync_status(self) -> Dict[str, Any]:
        """获取智能同步状态"""
        return {
            "enabled": bool(self.sync_directions),
            "running": self.is_running,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "last_fast_sync": self.last_fast_sync.isoformat() if self.last_fast_sync else None,
            "last_slow_sync": self.last_slow_sync.isoformat() if self.last_slow_sync else None,
            "directions": self.sync_directions,
            "strategies": {
                data_type: {
                    "priority": config["priority"].value,
                    "strategy": config["strategy"].value,
                    "interval": config["sync_interval"],
                    "description": config["description"]
                }
                for data_type, config in self.data_sync_strategies.items()
            },
            "hot_projects_count": len(self.recently_accessed_projects),
            "external_db_type": db_manager.database_type if db_manager.external_engine else None,
            "external_db_configured": bool(db_manager.external_url),
            "r2_configured": bool(os.getenv("R2_ACCESS_KEY_ID"))
        }


# 创建全局智能同步管理器实例
smart_sync_manager = DataSyncManager()


async def start_smart_sync():
    """启动智能数据同步服务"""
    await smart_sync_manager.start_smart_sync()


async def get_smart_sync_status():
    """获取智能同步状态"""
    return await smart_sync_manager.get_sync_status()


async def mark_project_accessed(project_id: str):
    """标记项目被访问"""
    smart_sync_manager.mark_project_accessed(project_id)
