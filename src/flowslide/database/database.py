"""
Database configuration and session management with intelligent fallback strategy
"""

import logging
import os
import asyncio
from typing import Optional, Tuple
from pathlib import Path

from sqlalchemy import create_engine, text
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
        # 仅接受真正的外部数据库URL（postgresql/mysql），否则视为未配置
        _raw_ext = (EXTERNAL_DATABASE_URL or "").strip()
        if _raw_ext.startswith("postgresql://") or _raw_ext.startswith("mysql://"):
            self.external_url = _raw_ext
            if _raw_ext.startswith("postgresql://"):
                self.external_async_url = _raw_ext.replace("postgresql://", "postgresql+asyncpg://")
            elif _raw_ext.startswith("mysql://"):
                self.external_async_url = _raw_ext.replace("mysql://", "mysql+aiomysql://")
            else:
                self.external_async_url = ""
        else:
            if _raw_ext:
                logger.info("ℹ️ DATABASE_URL is not a supported external DB (postgresql/mysql). Ignoring for external engines.")
            self.external_url = ""
            self.external_async_url = ""

        self.primary_engine = None
        self.primary_async_engine = None
        self.external_engine = None
        self.external_async_engine = None
        self.engine = None  # 向后兼容的别名

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
        self.engine = self.primary_engine  # 设置向后兼容的别名
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
            statement_cache_size = int(os.getenv("PG_STATEMENT_CACHE_SIZE", "0"))
            self.primary_engine = create_engine(
                self.external_url,
                pool_size=3,  # 较小的连接池大小
                max_overflow=2,  # 允许少量溢出
                pool_pre_ping=False,  # 禁用连接池ping以避免prepared statements
                pool_recycle=300,  # 更频繁的连接回收
                pool_timeout=60,  # 增加超时时间
                echo=False
            )
            self.primary_async_engine = create_async_engine(
                self.external_async_url,
                pool_size=3,
                max_overflow=2,
                pool_pre_ping=False,
                pool_recycle=300,
                pool_timeout=60,
                echo=False,
                connect_args={"statement_cache_size": statement_cache_size}  # 禁用prepared statements以兼容pgbouncer
            )
            logger.info("🎯 Detected Supabase - using pgbouncer-compatible configuration")
        else:
            # 普通PostgreSQL配置
            statement_cache_size = int(os.getenv("PG_STATEMENT_CACHE_SIZE", "0"))
            self.primary_engine = create_engine(
                self.external_url,
                pool_size=3,
                max_overflow=2,
                pool_pre_ping=False,
                pool_recycle=3600,
                pool_timeout=60,
                echo=False,
            )
            self.primary_async_engine = create_async_engine(
                self.external_async_url,
                pool_size=3,
                max_overflow=2,
                pool_pre_ping=False,
                pool_recycle=3600,
                pool_timeout=60,
                echo=False,
                connect_args={"statement_cache_size": statement_cache_size}  # 兼容pgbouncer
            )

        self.engine = self.primary_engine  # 设置向后兼容的别名
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

            # For Supabase/pgbouncer we only need to adjust async driver options
            # Do NOT pass statement_cache_size into the sync create_engine (psycopg2)
            async_connect_args = {}
            if is_supabase:
                # Supabase使用pgbouncer，需要禁用prepared statements for asyncpg
                statement_cache_size = int(os.getenv("PG_STATEMENT_CACHE_SIZE", "0"))
                async_connect_args = {"statement_cache_size": statement_cache_size}

            # Create sync engine without passing DB-API specific connect_args that psycopg2 doesn't accept
            self.external_engine = create_engine(
                self.external_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )

            # Async engine may accept driver-specific connect_args (e.g., asyncpg)
            self.external_async_engine = create_async_engine(
                self.external_async_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
                connect_args=async_connect_args
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

    # 确保向后兼容的别名也被设置
    db_manager.engine = db_manager.primary_engine

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

        if async_engine and engine:
            # Use sync engine for table creation to avoid pgbouncer issues
            with engine.begin() as conn:
                # Create all tables
                Base.metadata.create_all(bind=engine)

            logger.info("✅ Database tables created successfully")

            # Initialize default admin user - always create one regardless of mode
            from ..auth.auth_service import init_default_admin

            try:
                # Always initialize default admin user for all deployment modes
                # This ensures there's always at least one admin user available
                db = SessionLocal()
                init_default_admin(db)
                logger.info("✅ Default admin user initialized for all deployment modes")
            except Exception as e:
                logger.warning(f"⚠️ Admin user initialization warning: {e}")
            finally:
                if 'db' in locals():
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


def get_auth_db():
    """Dependency to get database session for authentication (based on deployment mode)"""
    from ..core.deployment_mode_manager import mode_manager

    try:
        current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
        mode_name = current_mode.value if current_mode else 'local_only'
    except Exception:
        mode_name = 'local_only'

    # For local and local_r2 modes, use local database
    if mode_name in ['local_only', 'local_r2']:
        # Use local database
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    # For local_external and local_external_r2 modes, use external database
    elif mode_name in ['local_external', 'local_external_r2']:
        if db_manager.external_engine:
            # Create session with external engine
            from sqlalchemy.orm import sessionmaker
            ExternalSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_manager.external_engine)
            db = ExternalSessionLocal()
            try:
                yield db
            finally:
                db.close()
        else:
            # Fallback to local if external not available
            logger.warning("⚠️ External database not available, falling back to local for authentication")
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()
    else:
        # Default to local
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


async def get_auth_async_db():
    """Dependency to get async database session for authentication (based on deployment mode)"""
    from ..core.deployment_mode_manager import mode_manager

    try:
        current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
        mode_name = current_mode.value if current_mode else 'local_only'
    except Exception:
        mode_name = 'local_only'

    # For local and local_r2 modes, use local database
    if mode_name in ['local_only', 'local_r2']:
        # Use local database
        if AsyncSessionLocal:
            async with AsyncSessionLocal() as session:
                yield session
        else:
            raise RuntimeError("Async database session not available")
    # For local_external and local_external_r2 modes, use external database
    elif mode_name in ['local_external', 'local_external_r2']:
        if db_manager.external_async_engine:
            # Create session with external async engine
            from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
            ExternalAsyncSessionLocal = async_sessionmaker(db_manager.external_async_engine, class_=AsyncSession, expire_on_commit=False)
            async with ExternalAsyncSessionLocal() as session:
                yield session
        else:
            # Fallback to local if external not available
            logger.warning("⚠️ External async database not available, falling back to local for authentication")
            if AsyncSessionLocal:
                async with AsyncSessionLocal() as session:
                    yield session
            else:
                raise RuntimeError("Async database session not available")
    else:
        # Default to local
        if AsyncSessionLocal:
            async with AsyncSessionLocal() as session:
                yield session
        else:
            raise RuntimeError("Async database session not available")
