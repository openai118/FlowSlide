"""
部署模式切换配置管理器
管理模式切换相关的配置和参数
"""

import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class SwitchTrigger(Enum):
    """切换触发器"""
    AUTO = "auto"              # 自动检测
    MANUAL = "manual"          # 手动触发
    SCHEDULED = "scheduled"    # 定时切换
    LOAD_BASED = "load_based"  # 负载触发
    ERROR_BASED = "error_based"  # 错误触发


@dataclass
class ModeSwitchConfig:
    """模式切换配置"""
    enabled: bool = True
    auto_switch: bool = True
    check_interval: int = 60  # 秒
    max_switch_attempts: int = 3
    switch_timeout: int = 1800  # 30分钟
    rollback_enabled: bool = True
    data_backup_before_switch: bool = True
    notify_on_switch: bool = True
    maintenance_mode: bool = False

    # 模式特定配置
    force_mode: Optional[str] = None
    preferred_modes: List[str] = None
    restricted_modes: List[str] = None

    # 切换触发条件
    switch_triggers: List[str] = None
    load_threshold: float = 0.8
    error_rate_threshold: float = 0.1

    # 通知配置
    notification_webhook: Optional[str] = None
    notification_email: Optional[str] = None


class DeploymentConfigManager:
    """部署配置管理器"""

    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'deployment.json')
        self.current_config: Optional[ModeSwitchConfig] = None
        self._ensure_config_directory()

    def _ensure_config_directory(self):
        """确保配置目录存在"""
        config_dir = os.path.dirname(self.config_file)
        os.makedirs(config_dir, exist_ok=True)

    def load_config(self) -> ModeSwitchConfig:
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.current_config = ModeSwitchConfig(**data)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                self.current_config = self._get_default_config()
        else:
            self.current_config = self._get_default_config()

        return self.current_config

    def save_config(self, config: ModeSwitchConfig) -> bool:
        """保存配置"""
        try:
            data = {
                'enabled': config.enabled,
                'auto_switch': config.auto_switch,
                'check_interval': config.check_interval,
                'max_switch_attempts': config.max_switch_attempts,
                'switch_timeout': config.switch_timeout,
                'rollback_enabled': config.rollback_enabled,
                'data_backup_before_switch': config.data_backup_before_switch,
                'notify_on_switch': config.notify_on_switch,
                'maintenance_mode': config.maintenance_mode,
                'force_mode': config.force_mode,
                'preferred_modes': config.preferred_modes,
                'restricted_modes': config.restricted_modes,
                'switch_triggers': config.switch_triggers,
                'load_threshold': config.load_threshold,
                'error_rate_threshold': config.error_rate_threshold,
                'notification_webhook': config.notification_webhook,
                'notification_email': config.notification_email
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.current_config = config
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False

    def _get_default_config(self) -> ModeSwitchConfig:
        """获取默认配置"""
        return ModeSwitchConfig(
            enabled=True,
            auto_switch=True,
            check_interval=60,
            max_switch_attempts=3,
            switch_timeout=1800,
            rollback_enabled=True,
            data_backup_before_switch=True,
            notify_on_switch=True,
            maintenance_mode=False,
            preferred_modes=["local_external_r2", "local_external", "local_r2", "local_only"],
            restricted_modes=[],
            switch_triggers=["auto", "manual"],
            load_threshold=0.8,
            error_rate_threshold=0.1
        )

    def update_from_env(self) -> ModeSwitchConfig:
        """从环境变量更新配置"""
        if self.current_config is None:
            self.current_config = self._get_default_config()

        # 从环境变量更新配置
        env_mappings = {
            'DEPLOYMENT_MODE_ENABLED': ('enabled', lambda x: x.lower() == 'true'),
            'AUTO_MODE_SWITCH': ('auto_switch', lambda x: x.lower() == 'true'),
            'MODE_CHECK_INTERVAL': ('check_interval', int),
            'MAX_SWITCH_ATTEMPTS': ('max_switch_attempts', int),
            'SWITCH_TIMEOUT': ('switch_timeout', int),
            'ROLLBACK_ENABLED': ('rollback_enabled', lambda x: x.lower() == 'true'),
            'DATA_BACKUP_BEFORE_SWITCH': ('data_backup_before_switch', lambda x: x.lower() == 'true'),
            'NOTIFY_ON_SWITCH': ('notify_on_switch', lambda x: x.lower() == 'true'),
            'MAINTENANCE_MODE': ('maintenance_mode', lambda x: x.lower() == 'true'),
            'FORCE_DEPLOYMENT_MODE': ('force_mode', str),
            'LOAD_THRESHOLD': ('load_threshold', float),
            'ERROR_RATE_THRESHOLD': ('error_rate_threshold', float),
            'NOTIFICATION_WEBHOOK': ('notification_webhook', str),
            'NOTIFICATION_EMAIL': ('notification_email', str)
        }

        for env_var, (attr, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    setattr(self.current_config, attr, converter(value))
                except Exception as e:
                    print(f"转换环境变量 {env_var} 失败: {e}")

        # 处理列表类型的环境变量
        preferred_modes = os.getenv('PREFERRED_DEPLOYMENT_MODES')
        if preferred_modes:
            self.current_config.preferred_modes = [m.strip() for m in preferred_modes.split(',')]

        restricted_modes = os.getenv('RESTRICTED_DEPLOYMENT_MODES')
        if restricted_modes:
            self.current_config.restricted_modes = [m.strip() for m in restricted_modes.split(',')]

        switch_triggers = os.getenv('SWITCH_TRIGGERS')
        if switch_triggers:
            self.current_config.switch_triggers = [t.strip() for t in switch_triggers.split(',')]

        return self.current_config

    def get_config(self) -> ModeSwitchConfig:
        """获取当前配置"""
        if self.current_config is None:
            self.load_config()
            self.update_from_env()
        return self.current_config

    def is_mode_allowed(self, mode: str) -> bool:
        """检查模式是否被允许"""
        config = self.get_config()

        # 检查限制模式
        if mode in config.restricted_modes:
            return False

        return True

    def get_preferred_mode(self, available_modes: List[str]) -> Optional[str]:
        """获取首选模式"""
        config = self.get_config()

        if not config.preferred_modes:
            return None

        # 从首选模式中选择第一个可用的
        for preferred_mode in config.preferred_modes:
            if preferred_mode in available_modes:
                return preferred_mode

        return None

    def should_trigger_switch(self, trigger: SwitchTrigger, **kwargs) -> bool:
        """判断是否应该触发切换"""
        config = self.get_config()

        if not config.enabled:
            return False

        if trigger.value not in config.switch_triggers:
            return False

        # 根据触发器类型进行额外检查
        if trigger == SwitchTrigger.LOAD_BASED:
            current_load = kwargs.get('current_load', 0)
            return current_load > config.load_threshold

        elif trigger == SwitchTrigger.ERROR_BASED:
            error_rate = kwargs.get('error_rate', 0)
            return error_rate > config.error_rate_threshold

        return True

    def get_switch_timeout(self) -> int:
        """获取切换超时时间"""
        return self.get_config().switch_timeout

    def is_rollback_enabled(self) -> bool:
        """检查是否启用回滚"""
        return self.get_config().rollback_enabled

    def should_backup_before_switch(self) -> bool:
        """检查切换前是否需要备份"""
        return self.get_config().data_backup_before_switch

    def should_notify_on_switch(self) -> bool:
        """检查切换时是否需要通知"""
        return self.get_config().notify_on_switch

    def is_maintenance_mode(self) -> bool:
        """检查是否处于维护模式"""
        return self.get_config().maintenance_mode

    def get_notification_config(self) -> Dict[str, Optional[str]]:
        """获取通知配置"""
        config = self.get_config()
        return {
            'webhook': config.notification_webhook,
            'email': config.notification_email
        }

    def validate_mode_config(self, mode: str, config: Dict[str, Any]) -> bool:
        """验证模式配置"""
        from .sync_strategy_config import DeploymentMode

        try:
            mode_enum = DeploymentMode(mode.lower())
        except ValueError:
            return False

        # 验证必需的配置项
        required_configs = {
            DeploymentMode.LOCAL_ONLY: [],
            DeploymentMode.LOCAL_EXTERNAL: ['database_url'],
            DeploymentMode.LOCAL_R2: ['r2_access_key_id', 'r2_secret_access_key'],
            DeploymentMode.LOCAL_EXTERNAL_R2: ['database_url', 'r2_access_key_id', 'r2_secret_access_key']
        }

        required = required_configs.get(mode_enum, [])
        for key in required:
            if key not in config or not config[key]:
                return False

        # 验证数据库URL格式
        if 'database_url' in config:
            db_url = config['database_url']
            if mode_enum == DeploymentMode.LOCAL_EXTERNAL or mode_enum == DeploymentMode.LOCAL_EXTERNAL_R2:
                if not (db_url.startswith('postgresql://') or db_url.startswith('mysql://')):
                    return False

        # 验证R2配置
        if 'r2_access_key_id' in config and 'r2_secret_access_key' in config:
            if not config['r2_access_key_id'] or not config['r2_secret_access_key']:
                return False

        return True


# 全局配置管理器实例
config_manager = DeploymentConfigManager()


def get_deployment_config() -> ModeSwitchConfig:
    """获取部署配置"""
    return config_manager.get_config()


def save_deployment_config(config: ModeSwitchConfig) -> bool:
    """保存部署配置"""
    return config_manager.save_config(config)


def update_config_from_env() -> ModeSwitchConfig:
    """从环境变量更新配置"""
    return config_manager.update_from_env()
