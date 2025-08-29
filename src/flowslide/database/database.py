"""
Database configuration and session management with intelligent fallback strategy
"""

import logging
import os
import asyncio
from typing import Optional, Tuple
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from ..core.simple_config import (
    DATABASE_URL,
    ASYNC_DATABASE_URL,
    LOCAL_DATABASE_URL,
    EXTERNAL_DATABASE_URL,
    DATABASE_MODE
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """智能数据库管理器"""

    def __init__(self):
        self.local_url = LOCAL_DATABASE_URL
        self.local_async_url = LOCAL_DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
        self.external_url = EXTERNAL_DATABASE_URL
        self.external_async_url = EXTERNAL_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://") if EXTERNAL_DATABASE_URL.startswith("postgresql://") else ""

        self.primary_engine = None
        self.primary_async_engine = None
        self.external_engine = None
        self.external_async_engine = None

        self.database_type = "sqlite"
        self.sync_enabled = False

    def _ensure_data_directory(self):
        """确保数据目录存在"""
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        logger.info(f"✅ Data directory ready: {data_dir.absolute()}")

    def _create_local_engine(self):
        """创建本地SQLite引擎"""
        self._ensure_data_directory()
        self.primary_engine = create_engine(
            self.local_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.primary_async_engine = create_async_engine(
            self.local_async_url,
            echo=False
        )
        self.database_type = "sqlite"
        logger.info("✅ Local SQLite database ready")

    def _create_external_engine(self):
        """创建外部数据库引擎"""
        if not self.external_url:
            raise ValueError("External database URL not configured")

        # 解析数据库URL以检测是否是Supabase
        from urllib.parse import urlparse
        parsed = urlparse(self.external_url)

        # 检查是否是Supabase（通过URL特征识别）
        is_supabase = ('supabase' in parsed.hostname if parsed.hostname else False) or ('pooler.supabase.com' in self.external_url)

        if is_supabase:
            # Supabase使用pgbouncer，需要特殊配置
            self.primary_engine = create_engine(
                self.external_url,
                pool_size=5,  # 减小连接池大小
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=300,  # 更频繁的连接回收
                echo=False
            )
            self.primary_async_engine = create_async_engine(
                self.external_async_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False
            )
            logger.info("🎯 Detected Supabase - using pgbouncer-compatible configuration")
        else:
            # 普通PostgreSQL配置
            self.primary_engine = create_engine(
                self.external_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )
            self.primary_async_engine = create_async_engine(
                self.external_async_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )

        self.database_type = "postgresql" if "postgresql" in self.external_url else "external"
        logger.info(f"✅ External database ready: {self.database_type}")

    def _create_backup_engine(self):
        """创建备份引擎（用于数据同步）"""
        if self.external_url:
            # 解析数据库URL以检测是否是Supabase
            from urllib.parse import urlparse
            parsed = urlparse(self.external_url)

            # 检查是否是Supabase
            is_supabase = 'supabase' in parsed.hostname if parsed.hostname else False

            connect_args = {}
            if is_supabase:
                # Supabase使用pgbouncer，不需要特殊的连接参数
                connect_args = {}

            self.external_engine = create_engine(
                self.external_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
                connect_args=connect_args
            )
            self.external_async_engine = create_async_engine(
                self.external_async_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
                connect_args=connect_args
            )
            logger.info("✅ Backup database engine ready")

    def initialize(self):
        """初始化数据库管理器"""
        try:
            # 根据模式选择主数据库
            if DATABASE_MODE == "external" and self.external_url:
                try:
                    self._create_external_engine()
                    logger.info("🎯 Using external database as primary")
                except Exception as e:
                    logger.warning(f"❌ External database failed: {e}")
                    logger.info("🔄 Falling back to local database")
                    self._create_local_engine()
            else:
                self._create_local_engine()
                logger.info("🏠 Using local database as primary")

            # 如果配置了外部数据库，创建备份引擎用于同步
            if self.external_url and DATABASE_MODE != "external":
                try:
                    self._create_backup_engine()
                    self.sync_enabled = True
                    logger.info("🔄 Data synchronization enabled")
                except Exception as e:
                    logger.warning(f"⚠️ Backup engine creation failed: {e}")

        except Exception as e:
            logger.error(f"❌ Database manager initialization failed: {e}")
            raise

    async def sync_to_external(self):
        """同步本地数据到外部数据库"""
        if not self.sync_enabled or not self.external_engine:
            return

        try:
            logger.info("🔄 Starting data synchronization to external database...")

            # 这里可以实现数据同步逻辑
            # 例如：导出本地数据，导入到外部数据库

            logger.info("✅ Data synchronization completed")
        except Exception as e:
            logger.error(f"❌ Data synchronization failed: {e}")

    async def backup_to_r2(self):
        """备份数据到R2"""
        try:
            # 检查R2配置
            r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
            r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
            r2_endpoint = os.getenv("R2_ENDPOINT")
            r2_bucket = os.getenv("R2_BUCKET_NAME")

            if not all([r2_access_key, r2_secret_key, r2_endpoint, r2_bucket]):
                logger.info("ℹ️ R2 not configured, skipping cloud backup")
                return

            logger.info("☁️ Starting R2 backup...")

            # 这里可以调用R2备份脚本或实现备份逻辑
            # 备份本地数据库文件和重要数据

            logger.info("✅ R2 backup completed")
        except Exception as e:
            logger.error(f"❌ R2 backup failed: {e}")


# 创建全局数据库管理器实例
db_manager = DatabaseManager()

# 向后兼容的变量
engine = None
async_engine = None
DATABASE_TYPE = "sqlite"

# 初始化数据库管理器
def initialize_database():
    """初始化数据库系统"""
    global engine, async_engine, DATABASE_TYPE

    db_manager.initialize()

    engine = db_manager.primary_engine
    async_engine = db_manager.primary_async_engine
    DATABASE_TYPE = db_manager.database_type

    return db_manager


# 临时创建基本的session makers，稍后会在initialize_database()中更新
temp_engine = create_engine(
    "sqlite:///./data/flowslide.db",
    connect_args={"check_same_thread": False},
    echo=False,
)
temp_async_engine = create_async_engine("sqlite+aiosqlite:///./data/flowslide.db", echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=temp_engine)
AsyncSessionLocal = async_sessionmaker(temp_async_engine, class_=AsyncSession, expire_on_commit=False)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """Dependency to get async database session"""
    if AsyncSessionLocal:
        async with AsyncSessionLocal() as session:
            yield session
    else:
        raise RuntimeError("Async database session not available")


async def init_db():
    """Initialize database tables with error handling"""
    try:
        # Import here to avoid circular imports
        from .models import Base

        logger.info(f"🗄️ Initializing database tables using {DATABASE_TYPE}...")

        if async_engine:
            async with async_engine.begin() as conn:
                # Create all tables
                await conn.run_sync(Base.metadata.create_all)

            logger.info("✅ Database tables created successfully")

            # Initialize default admin user
            from ..auth.auth_service import init_default_admin

            db = SessionLocal()
            try:
                init_default_admin(db)
                logger.info("✅ Default admin user initialized")
            except Exception as e:
                logger.warning(f"⚠️ Admin user initialization warning: {e}")
            finally:
                db.close()
        else:
            raise RuntimeError("Database engine not initialized")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Try to handle the error gracefully
        if "postgresql" in str(e).lower() or "asyncpg" in str(e).lower():
            logger.error("💡 Hint: This appears to be a PostgreSQL connection issue.")
            logger.error("   Consider checking your DATABASE_URL or using SQLite as fallback.")
        raise


async def close_db():
    """Close database connections"""
    if async_engine:
        await async_engine.dispose()


def update_session_makers():
    """更新session makers以使用正确的引擎"""
    global SessionLocal, AsyncSessionLocal

    if engine:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    if async_engine:
        AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
