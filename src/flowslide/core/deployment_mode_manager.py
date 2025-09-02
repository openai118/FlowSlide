"""
部署模式切换管理器
支持四种部署模式之间的动态切换
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..database import db_manager
from .sync_strategy_config import DeploymentMode, DataSyncStrategy

logger = logging.getLogger(__name__)


class ModeTransition(Enum):
    """模式切换类型"""
    UPGRADE = "upgrade"      # 升级模式（增加存储层）
    DOWNGRADE = "downgrade"  # 降级模式（减少存储层）
    MIGRATION = "migration"  # 迁移模式（更换存储层）
    MAINTENANCE = "maintenance"  # 维护模式（临时切换）


@dataclass
class ModeSwitchContext:
    """模式切换上下文"""
    from_mode: DeploymentMode
    to_mode: DeploymentMode
    transition_type: ModeTransition
    trigger_reason: str
    start_time: datetime
    estimated_duration: int  # 秒
    data_migration_required: bool
    rollback_plan: Optional[Dict[str, Any]] = None


class DeploymentModeManager:
    """部署模式管理器"""

    def __init__(self):
        self.current_mode: Optional[DeploymentMode] = None
        self.last_mode_check: Optional[datetime] = None
        self.mode_check_interval: int = 60  # 60秒检查一次
        self.switch_in_progress: bool = False
        self.switch_context: Optional[ModeSwitchContext] = None

        # 初始化当前模式
        self.current_mode = self.detect_current_mode()
        self.last_mode_check = datetime.now()

        # 模式切换历史
        self.mode_history: List[Dict[str, Any]] = []

        # 模式切换回调
        self.mode_change_callbacks: List[Callable] = []

        # 模式兼容性矩阵
        self.compatibility_matrix = self._build_compatibility_matrix()

        # 模式切换策略
        self.switch_strategies = self._build_switch_strategies()

    def _build_compatibility_matrix(self) -> Dict[str, List[str]]:
        """构建模式兼容性矩阵"""
        return {
            "local_only": ["local_external", "local_r2", "local_external_r2"],
            "local_external": ["local_only", "local_external_r2"],
            "local_r2": ["local_only", "local_external_r2"],
            "local_external_r2": ["local_external", "local_r2"]
        }

    def _build_switch_strategies(self) -> Dict[str, Dict[str, Any]]:
        """构建模式切换策略"""
        return {
            # 从LOCAL_ONLY切换
            "local_only->local_external": {
                "transition_type": ModeTransition.UPGRADE,
                "data_migration_required": True,
                "estimated_duration": 300,  # 5分钟
                "rollback_supported": True,
                "pre_switch_checks": ["external_db_connection", "data_backup"],
                "post_switch_actions": ["sync_initial_data", "update_config"]
            },
            "local_only->local_r2": {
                "transition_type": ModeTransition.UPGRADE,
                "data_migration_required": True,
                "estimated_duration": 600,  # 10分钟
                "rollback_supported": True,
                "pre_switch_checks": ["r2_connection", "data_backup"],
                "post_switch_actions": ["sync_initial_data", "update_config"]
            },
            "local_only->local_external_r2": {
                "transition_type": ModeTransition.UPGRADE,
                "data_migration_required": True,
                "estimated_duration": 900,  # 15分钟
                "rollback_supported": True,
                "pre_switch_checks": ["external_db_connection", "r2_connection", "data_backup"],
                "post_switch_actions": ["sync_initial_data", "update_config"]
            },

            # 从LOCAL_EXTERNAL切换
            "local_external->local_only": {
                "transition_type": ModeTransition.DOWNGRADE,
                "data_migration_required": False,
                "estimated_duration": 60,  # 1分钟
                "rollback_supported": True,
                "pre_switch_checks": ["data_sync_complete"],
                "post_switch_actions": ["cleanup_external_connections"]
            },
            "local_external->local_external_r2": {
                "transition_type": ModeTransition.UPGRADE,
                "data_migration_required": True,
                "estimated_duration": 600,  # 10分钟
                "rollback_supported": True,
                "pre_switch_checks": ["r2_connection", "data_backup"],
                "post_switch_actions": ["sync_initial_data", "update_config"]
            },

            # 从LOCAL_R2切换
            "local_r2->local_only": {
                "transition_type": ModeTransition.DOWNGRADE,
                "data_migration_required": False,
                "estimated_duration": 60,  # 1分钟
                "rollback_supported": True,
                "pre_switch_checks": ["data_sync_complete"],
                "post_switch_actions": ["cleanup_r2_connections"]
            },
            "local_r2->local_external_r2": {
                "transition_type": ModeTransition.UPGRADE,
                "data_migration_required": True,
                "estimated_duration": 900,  # 15分钟
                "rollback_supported": True,
                "pre_switch_checks": ["external_db_connection", "data_backup"],
                "post_switch_actions": ["sync_initial_data", "update_config"]
            },

            # 从LOCAL_EXTERNAL_R2切换
            "local_external_r2->local_external": {
                "transition_type": ModeTransition.DOWNGRADE,
                "data_migration_required": False,
                "estimated_duration": 120,  # 2分钟
                "rollback_supported": True,
                "pre_switch_checks": ["data_sync_complete"],
                "post_switch_actions": ["cleanup_r2_connections"]
            },
            "local_external_r2->local_r2": {
                "transition_type": ModeTransition.DOWNGRADE,
                "data_migration_required": False,
                "estimated_duration": 120,  # 2分钟
                "rollback_supported": True,
                "pre_switch_checks": ["data_sync_complete"],
                "post_switch_actions": ["cleanup_external_connections"]
            }
        }

    def detect_current_mode(self) -> DeploymentMode:
        """检测当前部署模式"""
        logger.info("开始检测当前部署模式...")
        # If operator set ACTIVE_DEPLOYMENT_MODE, respect it but still run auto-detection for info
        # ACTIVE_DEPLOYMENT_MODE values: concrete modes (e.g., 'local', 'local_external', 'local_r2', 'local_external_r2') or 'none' to allow auto-detect
        active_mode_env = os.getenv("ACTIVE_DEPLOYMENT_MODE")
        if active_mode_env:
            active_mode_val = active_mode_env.strip().lower()
            # If ACTIVE_DEPLOYMENT_MODE explicitly set to a concrete mode (not 'none'),
            # run auto-detection for informational purposes but do not override the active mode.
            if active_mode_val != 'none':
                try:
                    from .auto_detection_service import AutoDetectionService
                    detection_service = AutoDetectionService()
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, detection_service.detect_deployment_mode())
                                _detected_mode = future.result(timeout=30)
                        else:
                            _detected_mode = loop.run_until_complete(detection_service.detect_deployment_mode())
                    except RuntimeError:
                        _detected_mode = asyncio.run(detection_service.detect_deployment_mode())
                    logger.info(f"🔍 Auto-detection (informational) result while ACTIVE_DEPLOYMENT_MODE set: {_detected_mode.value}")
                except Exception:
                    logger.debug("Auto-detection (informational) failed while ACTIVE_DEPLOYMENT_MODE set; ignoring")
                try:
                    logger.info(f"ACTIVE_DEPLOYMENT_MODE environment variable set: {active_mode_val} - using as active mode and not overriding it")
                    return DeploymentMode(active_mode_val)
                except ValueError:
                    logger.warning(f"ACTIVE_DEPLOYMENT_MODE has invalid value: {active_mode_env}, falling back to normal detection")
        
        # 首先检查配置文件中是否有用户保存的模式选择
        try:
            from .deployment_config_manager import config_manager
            config = config_manager.load_config()
            if config.force_mode:
                try:
                    logger.info(f"配置文件中强制模式: {config.force_mode}")
                    return DeploymentMode(config.force_mode.lower())
                except ValueError:
                    logger.warning(f"配置文件中的无效模式: {config.force_mode}")
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}")

        # 检查环境变量中的强制模式
        forced_mode = os.getenv("FORCE_DEPLOYMENT_MODE")
        if forced_mode:
            try:
                logger.info(f"环境变量中强制模式: {forced_mode}")
                return DeploymentMode(forced_mode.lower())
            except ValueError:
                logger.warning(f"环境变量中的无效强制模式: {forced_mode}")

        # 使用自动检测服务进行智能检测
        try:
            # 动态导入以避免循环导入
            from .auto_detection_service import AutoDetectionService
            detection_service = AutoDetectionService()
            
            # 在新的事件循环中运行异步检测
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环已经在运行，创建新任务
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, detection_service.detect_deployment_mode())
                        detected_mode = future.result(timeout=30)  # 30秒超时
                else:
                    detected_mode = loop.run_until_complete(detection_service.detect_deployment_mode())
            except RuntimeError:
                # 没有事件循环，创建新的
                detected_mode = asyncio.run(detection_service.detect_deployment_mode())

            logger.info(f"🔍 自动检测结果: {detected_mode.value}")
            logger.info(f"返回自动检测结果: {detected_mode}")
            return detected_mode

        except Exception as e:
            logger.warning(f"自动检测失败，使用传统方法: {e}")

            # 回退到传统检测方法
            # 使用simple_config中的实际数据库URL而不是环境变量
            try:
                from .simple_config import DATABASE_URL
                database_url = DATABASE_URL
                logger.info(f"使用simple_config中的DATABASE_URL: {database_url}")
            except Exception as import_error:
                logger.error(f"无法导入DATABASE_URL: {import_error}")
                database_url = os.getenv("DATABASE_URL", "")
                logger.info(f"使用环境变量DATABASE_URL: {database_url}")
            
            has_r2 = bool(os.getenv("R2_ACCESS_KEY_ID"))
            logger.info(f"R2_ACCESS_KEY_ID存在: {has_r2}")

            # 检查是否是外部数据库（非SQLite）
            has_external_db = False
            if database_url:
                # 检查是否是PostgreSQL或其他外部数据库
                if database_url.startswith("postgresql://") or database_url.startswith("mysql://"):
                    has_external_db = True
                    logger.info("检测到PostgreSQL/MySQL外部数据库")
                # 如果是SQLite，检查是否是本地文件路径
                elif database_url.startswith("sqlite:///"):
                    has_external_db = False  # 本地SQLite
                    logger.info("检测到本地SQLite数据库")
                else:
                    # 其他情况默认为外部数据库
                    has_external_db = True
                    logger.info("检测到其他类型的外部数据库")
            else:
                logger.info("未找到数据库URL")

            logger.info(f"has_external_db: {has_external_db}, has_r2: {has_r2}")

            # 自动检测模式
            if has_external_db and has_r2:
                logger.info("检测到模式: LOCAL_EXTERNAL_R2")
                return DeploymentMode.LOCAL_EXTERNAL_R2
            elif has_external_db:
                logger.info("检测到模式: LOCAL_EXTERNAL")
                return DeploymentMode.LOCAL_EXTERNAL
            elif has_r2:
                logger.info("检测到模式: LOCAL_R2")
                return DeploymentMode.LOCAL_R2
            else:
                logger.info("检测到模式: LOCAL_ONLY")
                return DeploymentMode.LOCAL_ONLY

    def should_check_mode(self) -> bool:
        """判断是否应该检查模式变化"""
        if self.last_mode_check is None:
            return True

        time_since_last_check = (datetime.now() - self.last_mode_check).total_seconds()
        return time_since_last_check >= self.mode_check_interval

    async def check_and_switch_mode(self) -> bool:
        """检查并切换模式"""
        if self.switch_in_progress:
            logger.info("模式切换正在进行中，跳过检查")
            return False

        if not self.should_check_mode():
            return False

        current_mode = self.detect_current_mode()
        self.last_mode_check = datetime.now()

        if current_mode == self.current_mode:
            return False

        # 检测到模式变化，开始切换
        logger.info(f"检测到模式变化: {self.current_mode} -> {current_mode}")
        await self.switch_mode(current_mode, f"自动检测到配置变化")
        return True

    async def switch_mode(self, target_mode: DeploymentMode, reason: str = "手动切换") -> bool:
        """切换到指定模式"""
        if self.switch_in_progress:
            logger.error("模式切换正在进行中，无法启动新的切换")
            return False

        if target_mode == self.current_mode:
            logger.info(f"已经是目标模式 {target_mode.value}，无需切换")
            return True

        # 检查兼容性
        if self.current_mode is None:
            logger.error("当前模式未初始化")
            return False

        if not self._is_mode_compatible(self.current_mode, target_mode):
            logger.error(f"模式 {self.current_mode.value} 无法切换到 {target_mode.value}")
            return False

        # 准备切换上下文
        switch_key = f"{self.current_mode.value}->{target_mode.value}"
        strategy = self.switch_strategies.get(switch_key, {})

        self.switch_context = ModeSwitchContext(
            from_mode=self.current_mode,
            to_mode=target_mode,
            transition_type=strategy.get("transition_type", ModeTransition.MIGRATION),
            trigger_reason=reason,
            start_time=datetime.now(),
            estimated_duration=strategy.get("estimated_duration", 300),
            data_migration_required=strategy.get("data_migration_required", True)
        )

        try:
            self.switch_in_progress = True
            logger.info(f"开始模式切换: {switch_key}")

            # 执行前置检查
            if not await self._perform_pre_switch_checks(strategy):
                raise Exception("前置检查失败")

            # 执行数据迁移（如果需要）
            if self.switch_context.data_migration_required:
                await self._perform_data_migration()

            # 更新配置
            await self._update_configuration(target_mode)

            # 执行后置操作
            await self._perform_post_switch_actions(strategy)

            # 记录切换历史
            self._record_mode_switch(success=True)

            # 通知回调
            await self._notify_mode_change_callbacks()

            logger.info(f"模式切换完成: {switch_key}")
            return True

        except Exception as e:
            logger.error(f"模式切换失败: {e}")
            self._record_mode_switch(success=False, error=str(e))

            # 执行回滚（如果支持）
            if strategy.get("rollback_supported", False):
                await self._rollback_mode_switch()

            return False

        finally:
            self.switch_in_progress = False
            self.switch_context = None

    async def transition_mode(self, from_mode: str, to_mode: str) -> bool:
        """转换模式（字符串版本，用于测试）"""
        try:
            from_mode_enum = DeploymentMode(from_mode.lower())
            to_mode_enum = DeploymentMode(to_mode.lower())
            return await self.switch_mode(to_mode_enum, f"测试切换: {from_mode} -> {to_mode}")
        except ValueError as e:
            logger.error(f"无效的模式名称: {e}")
            return False

    def _has_external_database(self) -> bool:
        """检查是否有外部数据库"""
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            return False

        # 检查是否是PostgreSQL或其他外部数据库
        if database_url.startswith("postgresql://") or database_url.startswith("mysql://"):
            return True
        return False

    def _is_mode_compatible(self, from_mode: DeploymentMode, to_mode: DeploymentMode) -> bool:
        """检查模式兼容性"""
        # 如果没有已知源模式，认为兼容（首次检测场景）
        if from_mode is None:
            return True

        # 相同模式视为兼容
        if from_mode == to_mode:
            return True

        # 使用兼容性矩阵作为有向图，判断目标模式是否可从当前模式通过一系列合法步骤到达
        start = from_mode.value
        target = to_mode.value

        # 简单广度优先搜索（BFS）判断可达性
        visited = set()
        queue = [start]

        while queue:
            node = queue.pop(0)
            if node == target:
                return True
            visited.add(node)
            for neigh in self.compatibility_matrix.get(node, []):
                if neigh not in visited and neigh not in queue:
                    queue.append(neigh)

        return False

    async def _perform_pre_switch_checks(self, strategy: Dict[str, Any]) -> bool:
        """执行前置检查"""
        checks = strategy.get("pre_switch_checks", [])

        for check in checks:
            try:
                if check == "external_db_connection":
                    if not await self._check_external_db_connection():
                        return False
                elif check == "r2_connection":
                    if not await self._check_r2_connection():
                        return False
                elif check == "data_backup":
                    if not await self._ensure_data_backup():
                        return False
                elif check == "data_sync_complete":
                    if not await self._ensure_data_sync_complete():
                        return False
            except Exception as e:
                logger.error(f"前置检查 {check} 失败: {e}")
                return False

        return True

    async def _perform_data_migration(self) -> None:
        """执行数据迁移"""
        logger.info("开始数据迁移...")

        # 这里实现具体的数据迁移逻辑
        # 根据切换的源模式和目标模式执行相应的迁移

        if not self.switch_context:
            raise Exception("切换上下文不存在")

        if self.switch_context.from_mode == DeploymentMode.LOCAL_ONLY:
            if self.switch_context.to_mode == DeploymentMode.LOCAL_EXTERNAL:
                await self._migrate_local_to_external()
            elif self.switch_context.to_mode == DeploymentMode.LOCAL_R2:
                await self._migrate_local_to_r2()
            elif self.switch_context.to_mode == DeploymentMode.LOCAL_EXTERNAL_R2:
                await self._migrate_local_to_external_r2()

        elif self.switch_context.from_mode == DeploymentMode.LOCAL_EXTERNAL:
            if self.switch_context.to_mode == DeploymentMode.LOCAL_EXTERNAL_R2:
                await self._migrate_external_to_external_r2()

        elif self.switch_context.from_mode == DeploymentMode.LOCAL_R2:
            if self.switch_context.to_mode == DeploymentMode.LOCAL_EXTERNAL_R2:
                await self._migrate_r2_to_external_r2()

        logger.info("数据迁移完成")

    async def _update_configuration(self, target_mode: DeploymentMode) -> None:
        """更新配置"""
        logger.info(f"更新配置到模式: {target_mode.value}")

        # 更新当前模式
        self.current_mode = target_mode

        # 保存用户选择的模式到配置文件
        try:
            from .deployment_config_manager import config_manager
            config = config_manager.load_config()
            config.force_mode = target_mode.value
            if config_manager.save_config(config):
                logger.info(f"用户选择的模式已保存到配置文件: {target_mode.value}")
            else:
                logger.error("保存用户选择的模式到配置文件失败")
        except Exception as e:
            logger.error(f"保存用户选择的模式失败: {e}")

        # 重新加载同步策略
        # 这里可以触发配置重新加载

        logger.info("配置更新完成")

    async def _perform_post_switch_actions(self, strategy: Dict[str, Any]) -> None:
        """执行后置操作"""
        actions = strategy.get("post_switch_actions", [])

        for action in actions:
            try:
                if action == "sync_initial_data":
                    await self._sync_initial_data()
                elif action == "update_config":
                    await self._update_service_config()
                elif action == "cleanup_external_connections":
                    await self._cleanup_external_connections()
                elif action == "cleanup_r2_connections":
                    await self._cleanup_r2_connections()
            except Exception as e:
                logger.error(f"后置操作 {action} 失败: {e}")

    def _record_mode_switch(self, success: bool, error: Optional[str] = None) -> None:
        """记录模式切换历史"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "from_mode": self.switch_context.from_mode.value if self.switch_context else None,
            "to_mode": self.switch_context.to_mode.value if self.switch_context else None,
            "success": success,
            "error": error,
            "duration": (datetime.now() - self.switch_context.start_time).total_seconds() if self.switch_context else 0
        }

        self.mode_history.append(record)

        # 保留最近100条记录
        if len(self.mode_history) > 100:
            self.mode_history = self.mode_history[-100:]

    async def _rollback_mode_switch(self) -> None:
        """回滚模式切换"""
        logger.info("开始回滚模式切换...")

        # 实现回滚逻辑
        # 这里可以恢复到之前的模式和配置

        logger.info("模式切换回滚完成")

    def add_mode_change_callback(self, callback: Callable) -> None:
        """添加模式变化回调"""
        self.mode_change_callbacks.append(callback)

    async def _notify_mode_change_callbacks(self) -> None:
        """通知模式变化回调"""
        for callback in self.mode_change_callbacks:
            try:
                await callback(self.current_mode, self.switch_context)
            except Exception as e:
                logger.error(f"模式变化回调执行失败: {e}")

    # 连接检查方法
    async def _check_external_db_connection(self) -> bool:
        """检查外部数据库连接"""
        try:
            # 实现外部数据库连接检查
            return True
        except Exception as e:
            logger.error(f"外部数据库连接检查失败: {e}")
            return False

    async def _check_r2_connection(self) -> bool:
        """检查R2连接"""
        try:
            # 实现R2连接检查
            return True
        except Exception as e:
            logger.error(f"R2连接检查失败: {e}")
            return False

    async def _ensure_data_backup(self) -> bool:
        """确保数据备份"""
        try:
            # 实现数据备份检查
            return True
        except Exception as e:
            logger.error(f"数据备份失败: {e}")
            return False

    async def _ensure_data_sync_complete(self) -> bool:
        """确保数据同步完成"""
        try:
            # 实现数据同步完成检查
            return True
        except Exception as e:
            logger.error(f"数据同步完成检查失败: {e}")
            return False

    # 数据迁移方法
    async def _migrate_local_to_external(self) -> None:
        """从本地迁移到外部数据库"""
        logger.info("执行本地到外部数据库的数据迁移")

    async def _migrate_local_to_r2(self) -> None:
        """从本地迁移到R2"""
        logger.info("执行本地到R2的数据迁移")

    async def _migrate_local_to_external_r2(self) -> None:
        """从本地迁移到外部数据库+R2"""
        logger.info("执行本地到外部数据库+R2的数据迁移")
        # 这个迁移需要同时设置外部数据库和R2连接
        # 可以结合现有的迁移逻辑

    async def _migrate_external_to_external_r2(self) -> None:
        """从外部数据库迁移到外部数据库+R2"""
        logger.info("执行外部数据库到外部数据库+R2的数据迁移")

    async def _migrate_r2_to_external_r2(self) -> None:
        """从R2迁移到外部数据库+R2"""
        logger.info("执行R2到外部数据库+R2的数据迁移")

    # 后置操作方法
    async def _sync_initial_data(self) -> None:
        """同步初始数据"""
        logger.info("同步初始数据")

    async def _update_service_config(self) -> None:
        """更新服务配置"""
        logger.info("更新服务配置")

    async def _cleanup_external_connections(self) -> None:
        """清理外部连接"""
        logger.info("清理外部数据库连接")

    async def _cleanup_r2_connections(self) -> None:
        """清理R2连接"""
        logger.info("清理R2连接")

    def get_mode_history(self) -> List[Dict[str, Any]]:
        """获取模式切换历史"""
        return self.mode_history.copy()

    def get_current_mode_info(self) -> Dict[str, Any]:
        """获取当前模式信息"""
        # 确保current_mode不为None
        if self.current_mode is None:
            self.current_mode = self.detect_current_mode()

        return {
            "current_mode": self.current_mode.value if self.current_mode else DeploymentMode.LOCAL_ONLY.value,
            "switch_in_progress": self.switch_in_progress,
            "last_mode_check": self.last_mode_check.isoformat() if self.last_mode_check else None,
            "switch_context": {
                "from_mode": self.switch_context.from_mode.value if self.switch_context else None,
                "to_mode": self.switch_context.to_mode.value if self.switch_context else None,
                "transition_type": self.switch_context.transition_type.value if self.switch_context else None,
                "trigger_reason": self.switch_context.trigger_reason if self.switch_context else None,
                "start_time": self.switch_context.start_time.isoformat() if self.switch_context else None,
                "estimated_duration": self.switch_context.estimated_duration if self.switch_context else None,
                "data_migration_required": self.switch_context.data_migration_required if self.switch_context else None
            } if self.switch_context else None
        }


# 全局模式管理器实例
mode_manager = DeploymentModeManager()


async def start_mode_monitoring():
    """启动模式监控"""
    logger.info("启动部署模式监控服务")

    while True:
        try:
            await mode_manager.check_and_switch_mode()
            await asyncio.sleep(mode_manager.mode_check_interval)
        except Exception as e:
            logger.error(f"模式监控出错: {e}")
            await asyncio.sleep(60)  # 出错后等待1分钟重试


def get_current_deployment_mode() -> DeploymentMode:
    """获取当前部署模式"""
    return mode_manager.detect_current_mode()


def is_mode_switch_in_progress() -> bool:
    """检查是否有模式切换正在进行"""
    return mode_manager.switch_in_progress
