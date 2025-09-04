"""
配置同步服务 - 专门处理系统配置和AI配置的双向同步
确保关键配置数据在不同部署模式下保持一致性
"""

import logging
import os
import time
from typing import Dict, List, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.database import SessionLocal
from ..database.models import SystemConfig, AIProviderConfig
from ..core.simple_config import (
    ai_config,
    app_config
)

logger = logging.getLogger(__name__)


class ConfigSyncService:
    """配置同步服务"""

    def __init__(self):
        self.sync_enabled = self._check_sync_enabled()

    def _check_sync_enabled(self) -> bool:
        """检查是否启用配置同步"""
        # 配置同步需要在外部数据库配置完整且指向非SQLite时启用
        db_url = (os.getenv("DATABASE_URL") or "").strip()
        has_external_db = db_url.startswith("postgresql://") or db_url.startswith("mysql://")
        sync_enabled = os.getenv("ENABLE_CONFIG_SYNC", "true").lower() == "true"
        return has_external_db and sync_enabled

    def sync_system_configs_from_env(self, session: Session):
        """从环境变量同步系统配置到数据库"""
        try:
            logger.info("🔄 Syncing system configs from environment variables")

            # 解析外部数据库URL，仅当为标准外部前缀时才视为有效
            ext_db_url = (os.getenv("DATABASE_URL") or "").strip()
            ext_db_url_is_valid = ext_db_url.startswith("postgresql://") or ext_db_url.startswith("mysql://")

            system_configs = [
                # 数据库配置
                # 仅在外部数据库配置为标准前缀时写入
                *([
                    {
                        "config_key": "database_url",
                        "config_value": ext_db_url,
                        "config_type": "password",
                        "category": "database",
                        "description": "外部数据库连接URL",
                        "is_sensitive": True,
                        "is_system": True
                    }
                ] if ext_db_url_is_valid else []),
                # 安全配置
                {
                    "config_key": "admin_username",
                    "config_value": os.getenv("ADMIN_USERNAME", "admin"),
                    "config_type": "text",
                    "category": "security",
                    "description": "管理员用户名",
                    "is_sensitive": False,
                    "is_system": True
                },
                {
                    "config_key": "admin_password",
                    "config_value": os.getenv("ADMIN_PASSWORD"),
                    "config_type": "password",
                    "category": "security",
                    "description": "管理员密码",
                    "is_sensitive": True,
                    "is_system": True
                },
                {
                    "config_key": "admin_email",
                    "config_value": os.getenv("ADMIN_EMAIL"),
                    "config_type": "text",
                    "category": "security",
                    "description": "管理员邮箱",
                    "is_sensitive": False,
                    "is_system": True
                },
                # R2配置
                {
                    "config_key": "r2_access_key_id",
                    "config_value": os.getenv("R2_ACCESS_KEY_ID"),
                    "config_type": "password",
                    "category": "storage",
                    "description": "R2访问密钥ID",
                    "is_sensitive": True,
                    "is_system": True
                },
                {
                    "config_key": "r2_secret_access_key",
                    "config_value": os.getenv("R2_SECRET_ACCESS_KEY"),
                    "config_type": "password",
                    "category": "storage",
                    "description": "R2秘密访问密钥",
                    "is_sensitive": True,
                    "is_system": True
                },
                {
                    "config_key": "r2_endpoint",
                    "config_value": os.getenv("R2_ENDPOINT"),
                    "config_type": "url",
                    "category": "storage",
                    "description": "R2端点URL",
                    "is_sensitive": False,
                    "is_system": True
                },
                {
                    "config_key": "r2_bucket_name",
                    "config_value": os.getenv("R2_BUCKET_NAME"),
                    "config_type": "text",
                    "category": "storage",
                    "description": "R2存储桶名称",
                    "is_sensitive": False,
                    "is_system": True
                }
            ]

            for config_data in system_configs:
                if config_data["config_value"]:  # 只同步有值的配置
                    self._upsert_system_config(session, config_data)

            logger.info("✅ System configs synced from environment")

        except Exception as e:
            logger.error(f"❌ Failed to sync system configs from env: {e}")

    def sync_ai_configs_from_env(self, session: Session):
        """从环境变量同步AI配置到数据库"""
        try:
            logger.info("🔄 Syncing AI configs from environment variables")

            ai_configs = [
                # OpenAI配置
                {
                    "provider_name": "openai",
                    "config_key": "api_key",
                    "config_value": ai_config.openai_api_key,
                    "config_type": "password",
                    "description": "OpenAI API密钥",
                    "is_active": True,
                    "priority": 1
                },
                {
                    "provider_name": "openai",
                    "config_key": "base_url",
                    "config_value": ai_config.openai_base_url,
                    "config_type": "url",
                    "description": "OpenAI API基础URL",
                    "is_active": True,
                    "priority": 1
                },
                {
                    "provider_name": "openai",
                    "config_key": "model",
                    "config_value": ai_config.openai_model,
                    "config_type": "text",
                    "description": "OpenAI模型名称",
                    "is_active": True,
                    "priority": 1
                },
                # Anthropic配置
                {
                    "provider_name": "anthropic",
                    "config_key": "api_key",
                    "config_value": ai_config.anthropic_api_key,
                    "config_type": "password",
                    "description": "Anthropic API密钥",
                    "is_active": True,
                    "priority": 2
                },
                {
                    "provider_name": "anthropic",
                    "config_key": "base_url",
                    "config_value": ai_config.anthropic_base_url,
                    "config_type": "url",
                    "description": "Anthropic API基础URL",
                    "is_active": True,
                    "priority": 2
                },
                {
                    "provider_name": "anthropic",
                    "config_key": "model",
                    "config_value": ai_config.anthropic_model,
                    "config_type": "text",
                    "description": "Anthropic模型名称",
                    "is_active": True,
                    "priority": 2
                },
                # Google配置
                {
                    "provider_name": "google",
                    "config_key": "api_key",
                    "config_value": ai_config.google_api_key,
                    "config_type": "password",
                    "description": "Google AI API密钥",
                    "is_active": True,
                    "priority": 3
                },
                {
                    "provider_name": "google",
                    "config_key": "base_url",
                    "config_value": ai_config.google_base_url,
                    "config_type": "url",
                    "description": "Google AI API基础URL",
                    "is_active": True,
                    "priority": 3
                },
                {
                    "provider_name": "google",
                    "config_key": "model",
                    "config_value": ai_config.google_model,
                    "config_type": "text",
                    "description": "Google AI模型名称",
                    "is_active": True,
                    "priority": 3
                },
                # Azure OpenAI配置
                {
                    "provider_name": "azure_openai",
                    "config_key": "api_key",
                    "config_value": ai_config.azure_openai_api_key,
                    "config_type": "password",
                    "description": "Azure OpenAI API密钥",
                    "is_active": True,
                    "priority": 4
                },
                {
                    "provider_name": "azure_openai",
                    "config_key": "endpoint",
                    "config_value": ai_config.azure_openai_endpoint,
                    "config_type": "url",
                    "description": "Azure OpenAI端点",
                    "is_active": True,
                    "priority": 4
                },
                {
                    "provider_name": "azure_openai",
                    "config_key": "api_version",
                    "config_value": ai_config.azure_openai_api_version,
                    "config_type": "text",
                    "description": "Azure OpenAI API版本",
                    "is_active": True,
                    "priority": 4
                },
                # Ollama配置
                {
                    "provider_name": "ollama",
                    "config_key": "base_url",
                    "config_value": ai_config.ollama_base_url,
                    "config_type": "url",
                    "description": "Ollama API基础URL",
                    "is_active": True,
                    "priority": 5
                },
                {
                    "provider_name": "ollama",
                    "config_key": "model",
                    "config_value": ai_config.ollama_model,
                    "config_type": "text",
                    "description": "Ollama模型名称",
                    "is_active": True,
                    "priority": 5
                },
                # 默认AI提供商
                {
                    "provider_name": "system",
                    "config_key": "default_ai_provider",
                    "config_value": ai_config.default_ai_provider,
                    "config_type": "text",
                    "description": "默认AI提供商",
                    "is_active": True,
                    "priority": 0
                }
            ]

            for config_data in ai_configs:
                if config_data["config_value"]:  # 只同步有值的配置
                    self._upsert_ai_config(session, config_data)

            logger.info("✅ AI configs synced from environment")

        except Exception as e:
            logger.error(f"❌ Failed to sync AI configs from env: {e}")

    def _upsert_system_config(self, session: Session, config_data: Dict[str, Any]):
        """插入或更新系统配置"""
        try:
            existing = session.execute(
                select(SystemConfig).where(SystemConfig.config_key == config_data["config_key"])
            ).scalar_one_or_none()

            if existing:
                # 更新现有配置
                existing.config_value = config_data["config_value"]
                existing.updated_at = time.time()
            else:
                # 创建新配置
                new_config = SystemConfig(
                    config_key=config_data["config_key"],
                    config_value=config_data["config_value"],
                    config_type=config_data["config_type"],
                    category=config_data["category"],
                    description=config_data["description"],
                    is_sensitive=config_data["is_sensitive"],
                    is_system=config_data["is_system"],
                    created_at=time.time(),
                    updated_at=time.time()
                )
                session.add(new_config)

        except Exception as e:
            logger.error(f"❌ Failed to upsert system config {config_data['config_key']}: {e}")

    def _upsert_ai_config(self, session: Session, config_data: Dict[str, Any]):
        """插入或更新AI配置"""
        try:
            existing = session.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.provider_name == config_data["provider_name"],
                    AIProviderConfig.config_key == config_data["config_key"]
                )
            ).scalar_one_or_none()

            if existing:
                # 更新现有配置
                existing.config_value = config_data["config_value"]
                existing.updated_at = time.time()
            else:
                # 创建新配置
                new_config = AIProviderConfig(
                    provider_name=config_data["provider_name"],
                    config_key=config_data["config_key"],
                    config_value=config_data["config_value"],
                    config_type=config_data["config_type"],
                    description=config_data["description"],
                    is_active=config_data["is_active"],
                    priority=config_data["priority"],
                    created_at=time.time(),
                    updated_at=time.time()
                )
                session.add(new_config)

        except Exception as e:
            logger.error(f"❌ Failed to upsert AI config {config_data['provider_name']}.{config_data['config_key']}: {e}")

    def sync_configs_to_env(self, session: Session):
        """从数据库同步配置到环境变量"""
        try:
            logger.info("🔄 Syncing configs from database to environment")

            # 同步系统配置
            system_configs = session.execute(
                select(SystemConfig).where(SystemConfig.is_system == True)
            ).scalars().all()

            for config in system_configs:
                env_key = config.config_key.upper()
                if config.config_value and not os.getenv(env_key):
                    os.environ[env_key] = config.config_value
                    logger.debug(f"✅ Set env {env_key}")

            # 同步AI配置
            ai_configs = session.execute(select(AIProviderConfig)).scalars().all()

            for config in ai_configs:
                env_key = f"{config.provider_name.upper()}_{config.config_key.upper()}"
                if config.config_value and not os.getenv(env_key):
                    os.environ[env_key] = config.config_value
                    logger.debug(f"✅ Set env {env_key}")

            logger.info("✅ Configs synced to environment")

        except Exception as e:
            logger.error(f"❌ Failed to sync configs to env: {e}")

    def initialize_configs(self):
        """初始化配置数据"""
        if not self.sync_enabled:
            logger.info("🔄 Config sync disabled")
            return

        try:
            with SessionLocal() as session:
                # 从环境变量同步到数据库
                self.sync_system_configs_from_env(session)
                self.sync_ai_configs_from_env(session)

                # 从数据库同步到环境变量
                self.sync_configs_to_env(session)

                session.commit()

            logger.info("✅ Config initialization completed")

        except Exception as e:
            logger.error(f"❌ Failed to initialize configs: {e}")

    def get_system_config(self, config_key: str, session: Optional[Session] = None) -> Optional[str]:
        """获取系统配置值"""
        try:
            if session is None:
                with SessionLocal() as session:
                    config = session.execute(
                        select(SystemConfig).where(SystemConfig.config_key == config_key)
                    ).scalar_one_or_none()
                    return config.config_value if config else None
            else:
                config = session.execute(
                    select(SystemConfig).where(SystemConfig.config_key == config_key)
                ).scalar_one_or_none()
                return config.config_value if config else None

        except Exception as e:
            logger.error(f"❌ Failed to get system config {config_key}: {e}")
            return None

    def get_ai_config(self, provider_name: str, config_key: str, session: Optional[Session] = None) -> Optional[str]:
        """获取AI配置值"""
        try:
            if session is None:
                with SessionLocal() as session:
                    config = session.execute(
                        select(AIProviderConfig).where(
                            AIProviderConfig.provider_name == provider_name,
                            AIProviderConfig.config_key == config_key
                        )
                    ).scalar_one_or_none()
                    return config.config_value if config else None
            else:
                config = session.execute(
                    select(AIProviderConfig).where(
                        AIProviderConfig.provider_name == provider_name,
                        AIProviderConfig.config_key == config_key
                    )
                ).scalar_one_or_none()
                return config.config_value if config else None

        except Exception as e:
            logger.error(f"❌ Failed to get AI config {provider_name}.{config_key}: {e}")
            return None


# 创建全局配置同步服务实例
config_sync_service = ConfigSyncService()


def initialize_config_sync():
    """初始化配置同步"""
    config_sync_service.initialize_configs()


def get_system_config(config_key: str) -> Optional[str]:
    """获取系统配置的便捷函数"""
    return config_sync_service.get_system_config(config_key)


def get_ai_config(provider_name: str, config_key: str) -> Optional[str]:
    """获取AI配置的便捷函数"""
    return config_sync_service.get_ai_config(provider_name, config_key)
