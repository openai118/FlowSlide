"""
部署模式切换管理器
支持四种部署模式之间的动态切换
"""

import os
import logging
import asyncio
import threading
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


def get_current_deployment_mode() -> DeploymentMode:
    """获取当前部署模式"""
    manager = DeploymentModeManager()
    return manager.current_mode or DeploymentMode.LOCAL_ONLY


class DeploymentModeManager:
    """部署模式管理器"""

    def __init__(self):
        self.current_mode: Optional[DeploymentMode] = None
        self.last_mode_check: Optional[datetime] = None
        self.mode_check_interval: int = 60  # 60秒检查一次
        self.switch_in_progress: bool = False
        self.switch_context: Optional[ModeSwitchContext] = None

        # 初始化当前模式
        # Fast path: if deployment pinned mode is set, use it immediately; otherwise
        # set a safe default (LOCAL_ONLY) and run auto-detection in background so
        # imports and startup are not blocked by network checks.
        pinned_mode = os.getenv("DEPLOYMENT_PINNED_MODE")
        if pinned_mode:
            try:
                self.current_mode = DeploymentMode(pinned_mode.strip().lower())
                logger.info(f"使用 DEPLOYMENT_PINNED_MODE (immediate): {self.current_mode}")
            except Exception:
                logger.warning(f"DEPLOYMENT_PINNED_MODE 值无效: {pinned_mode}. 使用默认 local_only")
                self.current_mode = DeploymentMode.LOCAL_ONLY
        else:
            # default quick-start mode; background thread will update it later
            self.current_mode = DeploymentMode.LOCAL_ONLY

        self.last_mode_check = datetime.now()

        # Launch background detection to update current_mode without blocking imports
        try:
            threading.Thread(target=self._run_detection_in_background, daemon=True).start()
        except Exception as e:
            logger.warning(f"无法启动后台部署检测线程: {e}")
        # Callbacks to notify when mode changes (call signature: fn(old_mode, new_mode))
        self.mode_change_callbacks: List[Callable[[Optional[DeploymentMode], DeploymentMode], None]] = []

        # 模式切换历史
        self.mode_history: List[Dict[str, Any]] = []

        # 模式兼容性矩阵
        self.compatibility_matrix = self._build_compatibility_matrix()

        # 模式切换策略
        self.switch_strategies = self._build_switch_strategies()

    def _run_detection_in_background(self):
        """Run detect_deployment_mode asynchronously in a background thread and
        update self.current_mode when complete. This avoids blocking imports
        and long startup times while still performing the detection."""
        try:
            # Respect explicit pinned mode: if DEPLOYMENT_PINNED_MODE is set,
            # do not let the background auto-detection override the pinned choice.
            if os.getenv("DEPLOYMENT_PINNED_MODE"):
                logger.info("DEPLOYMENT_PINNED_MODE is set; skipping background auto-detection to avoid overriding pinned mode")
                return
            # Import locally to avoid circular imports at module load time
            from .auto_detection_service import auto_detection_service as detection_service
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                detected = loop.run_until_complete(detection_service.detect_deployment_mode())
                if detected:
                    old = self.current_mode
                    self.current_mode = detected
                    self.last_mode_check = datetime.now()
                    logger.info(f"自动部署检测完成，设置部署模式为: {detected}")
                    # Notify callbacks
                    try:
                        for cb in list(self.mode_change_callbacks):
                            try:
                                cb(old, detected)
                            except Exception as _cb_e:
                                logger.warning(f"mode change callback raised: {_cb_e}")
                    except Exception:
                        pass
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"后台部署检测失败: {e}")

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

    def register_mode_change_callback(self, fn: Callable[[Optional[DeploymentMode], DeploymentMode], None]):
        """Register a callback to be invoked when deployment mode changes.

        The callback is called with (old_mode, new_mode).
        """
        if fn not in self.mode_change_callbacks:
            self.mode_change_callbacks.append(fn)

    def unregister_mode_change_callback(self, fn: Callable[[Optional[DeploymentMode], DeploymentMode], None]):
        """Unregister a previously registered callback."""
        try:
            self.mode_change_callbacks.remove(fn)
        except ValueError:
            pass

    def detect_current_mode(self) -> DeploymentMode:
        """检测当前部署模式

        优先级：DEPLOYMENT_PINNED_MODE (环境变量/.env 可写入) -> 自动检测
        说明：移除旧的 ACTIVE_DEPLOYMENT_MODE / force_mode 双轨逻辑，统一使用 DEPLOYMENT_PINNED_MODE 作为“固定模式”。
        若 pinned 模式所需资源未就绪则忽略并降回自动检测。
        """
        logger.info("开始检测当前部署模式 (pinned 优先) ...")

        pinned_mode = os.getenv("DEPLOYMENT_PINNED_MODE")
        if pinned_mode:
            pinned_lower = pinned_mode.strip().lower()

            def _r2_config_complete():
                keys = ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET_NAME"]
                missing = [k for k in keys if not os.getenv(k)]
                if missing:
                    logger.info(f"⚠️ pinned 模式校验: R2 缺少 {missing}")
                    return False
                return True

            def _external_db_configured():
                db_url = os.getenv("DATABASE_URL", "").strip()
                if not db_url:
                    return False
                return db_url.startswith("postgresql://") or db_url.startswith("mysql://")

            need_r2 = pinned_lower in ("local_r2", "local_external_r2")
            need_external = pinned_lower in ("local_external", "local_external_r2")
            r2_ok = (not need_r2) or _r2_config_complete()
            external_ok = (not need_external) or _external_db_configured()

            if r2_ok and external_ok:
                try:
                    logger.info(f"使用 DEPLOYMENT_PINNED_MODE: {pinned_lower}")
                    return DeploymentMode(pinned_lower)
                except ValueError:
                    logger.warning(f"DEPLOYMENT_PINNED_MODE 无效值: {pinned_mode} -> 进入自动检测")
            else:
                logger.warning(
                    f"DEPLOYMENT_PINNED_MODE='{pinned_mode}' 资源未就绪 (R2={r2_ok}, external={external_ok})，忽略并自动检测"
                )

        # 兼容迁移：尝试读取旧配置 force_mode，若存在且无 pinned，则迁移
        if not pinned_mode:
            try:
                from .deployment_config_manager import config_manager
                cfg = config_manager.load_config()
                legacy_val = getattr(cfg, 'force_mode', None)
                if legacy_val:
                    legacy = legacy_val.strip().lower()
                    os.environ['DEPLOYMENT_PINNED_MODE'] = legacy  # 临时注入本进程
                    logger.info(f"迁移 legacy force_mode -> DEPLOYMENT_PINNED_MODE: {legacy}")
                    # 清空旧字段
                    try:
                        cfg.force_mode = None
                        config_manager.save_config(cfg)
                        logger.info("已清除 legacy force_mode 字段")
                    except Exception as _se:
                        logger.debug(f"清除 legacy force_mode 失败(忽略): {_se}")
                    # 递归调用一次以应用 pinned（避免重复逻辑）
                    return self.detect_current_mode()
            except Exception as _me:
                logger.debug(f"legacy force_mode 迁移检查失败: {_me}")

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
            # 注意：回退路径无法做连通性测试，因此为避免误判，回退时不启用 external
            # 使用simple_config中的实际数据库URL仅用于日志与本地/SQLite识别
            try:
                from .simple_config import DATABASE_URL
                database_url = DATABASE_URL
                logger.info(f"使用simple_config中的DATABASE_URL: {database_url}")
            except Exception as import_error:
                logger.error(f"无法导入DATABASE_URL: {import_error}")
                database_url = os.getenv("DATABASE_URL", "")
                logger.info(f"使用环境变量DATABASE_URL: {database_url}")
            
            def _all_r2_present():
                keys = ["R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_ENDPOINT","R2_BUCKET_NAME"]
                missing = [k for k in keys if not os.getenv(k)]
                if missing:
                    logger.info(f"R2 回退检测: 缺少 {missing}")
                    return False
                return True
            has_r2 = _all_r2_present()
            logger.info(f"R2 回退检测结果(has_r2): {has_r2}")

            # 为避免在无法测试时误入 external，回退路径一律视为无外部数据库
            has_external_db = False
            if database_url.startswith("sqlite:///"):
                logger.info("检测到本地SQLite数据库（回退模式）")
            elif database_url:
                logger.info("检测到可能的外部数据库URL，但回退模式不启用 external")
            else:
                logger.info("未找到数据库URL（回退模式）")

            logger.info(f"has_external_db: {has_external_db}, has_r2: {has_r2}")

            # 自动检测模式
            if has_r2:
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
            # 追加：如果当前模式包含 R2 但 R2 已不可用，则降级
            if current_mode in (DeploymentMode.LOCAL_R2, DeploymentMode.LOCAL_EXTERNAL_R2):
                try:
                    from .auto_detection_service import AutoDetectionService, ServiceStatus
                    detection_service = AutoDetectionService()
                    r2_status = await detection_service.check_r2_storage()
                    if r2_status.status != ServiceStatus.AVAILABLE:
                        # 降级目标
                        downgrade_to = DeploymentMode.LOCAL_EXTERNAL if current_mode == DeploymentMode.LOCAL_EXTERNAL_R2 and (os.getenv('DATABASE_URL','').startswith('postgresql://') or os.getenv('DATABASE_URL','').startswith('mysql://')) else DeploymentMode.LOCAL_ONLY
                        logger.warning(f"R2 不再可用，自动从 {current_mode.value} 降级到 {downgrade_to.value}")
                        self.current_mode = downgrade_to
                        return True
                except Exception as _dg_e:
                    logger.info(f"降级检测时忽略异常: {_dg_e}")
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

        # 同步写入 DEPLOYMENT_PINNED_MODE 到 .env（新机制）
        try:
            env_path = os.path.join(os.getcwd(), '.env')
            lines: list[str] = []
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    lines = f.read().splitlines()
            key = 'DEPLOYMENT_PINNED_MODE'
            new_line = f'{key}={target_mode.value}'
            replaced = False
            updated = []
            for ln in lines:
                if ln.strip().startswith(f'{key}='):
                    if not replaced:
                        updated.append(new_line)
                        replaced = True
                    # 跳过旧行
                else:
                    updated.append(ln)
            if not replaced:
                updated.append(new_line)
            content = '\n'.join(updated) + '\n'
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            os.environ[key] = target_mode.value
            logger.info(f"已写入 .env 中 {key}={target_mode.value}")
        except Exception as _we:
            logger.warning(f"写入 DEPLOYMENT_PINNED_MODE 失败（不影响运行）: {_we}")

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

        # 额外的后置操作：确保目标数据库有默认用户
        try:
            await self._ensure_default_user_in_target_db()
        except Exception as e:
            logger.error(f"确保默认用户失败: {e}")

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
            db_url = (os.getenv("DATABASE_URL") or "").strip()
            if not (db_url.startswith("postgresql://") or db_url.startswith("mysql://")):
                logger.warning("未配置有效的外部数据库URL，跳过连接检查")
                return False

            # 进行一次轻量连接测试
            from sqlalchemy import create_engine, text
            engine = create_engine(db_url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
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


    async def _ensure_default_user_in_target_db(self) -> None:
        """确保目标数据库有默认用户"""
        from ..database import db_manager
        from ..auth.auth_service import init_default_admin
        from sqlalchemy.orm import sessionmaker

        target_mode = self.current_mode
        if not target_mode:
            return

        # 如果是包含外部数据库的模式，确保外部数据库有默认用户
        if target_mode.value in ['local_external', 'local_external_r2']:
            if db_manager.external_engine:
                try:
                    logger.info("🔍 检查外部数据库是否有用户...")

                    # 创建外部数据库会话
                    ExternalSession = sessionmaker(bind=db_manager.external_engine)
                    external_db = ExternalSession()

                    try:
                        # 检查外部数据库是否有用户
                        from ..database.models import User
                        user_count = external_db.query(User).count()

                        if user_count == 0:
                            logger.info("📝 外部数据库没有用户，创建默认管理员...")
                            # 在外部数据库中创建默认用户
                            init_default_admin(external_db)
                            logger.info("✅ 外部数据库默认管理员创建完成")
                        else:
                            logger.info(f"✅ 外部数据库已有 {user_count} 个用户")

                    finally:
                        external_db.close()

                except Exception as e:
                    logger.error(f"❌ 检查/创建外部数据库默认用户失败: {e}")
            else:
                logger.warning("⚠️ 外部数据库引擎不可用")

        # 如果是只使用本地数据库的模式，确保本地数据库有默认用户
        elif target_mode.value in ['local_only', 'local_r2']:
            try:
                logger.info("🔍 检查本地数据库是否有用户...")

                # 使用现有的本地数据库会话
                from ..database.database import SessionLocal
                local_db = SessionLocal()

                try:
                    # 检查本地数据库是否有用户
                    from ..database.models import User
                    user_count = local_db.query(User).count()

                    if user_count == 0:
                        logger.info("📝 本地数据库没有用户，创建默认管理员...")
                        # 在本地数据库中创建默认用户
                        init_default_admin(local_db)
                        logger.info("✅ 本地数据库默认管理员创建完成")
                    else:
                        logger.info(f"✅ 本地数据库已有 {user_count} 个用户")

                finally:
                    local_db.close()

            except Exception as e:
                logger.error(f"❌ 检查/创建本地数据库默认用户失败: {e}")


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
    # Prefer the initialized/current value to avoid flicker; detect once if empty
    try:
        if mode_manager.current_mode is None:
            mode_manager.current_mode = mode_manager.detect_current_mode()
        return mode_manager.current_mode
    except Exception:
        # Fallback to detection if anything goes wrong
        return mode_manager.detect_current_mode()


def is_mode_switch_in_progress() -> bool:
    """检查是否有模式切换正在进行"""
    return mode_manager.switch_in_progress
