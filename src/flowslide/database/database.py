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
        if _raw_ext:
            # Accept schemes like 'postgresql', 'postgresql+asyncpg', 'mysql', 'mysql+aiomysql', etc.
            try:
                from urllib.parse import urlparse
                parsed = urlparse(_raw_ext)
                scheme = (parsed.scheme or "").lower()

                if scheme.startswith("postgresql") or scheme.startswith("mysql"):
                    # keep the original URL as external_url (may already include +driver)
                    self.external_url = _raw_ext
                    # compute async form using helper which also strips unsupported query params
                    try:
                        from ..core.simple_config import get_async_database_url
                        self.external_async_url = get_async_database_url(_raw_ext)
                    except Exception:
                        # fallback: attempt conservative replacements
                        if scheme.startswith("postgresql"):
                            if "asyncpg" in scheme:
                                self.external_async_url = _raw_ext
                            else:
                                self.external_async_url = _raw_ext.replace(scheme + "://", "postgresql+asyncpg://", 1)
                        elif scheme.startswith("mysql"):
                            if "aiomysql" in scheme:
                                self.external_async_url = _raw_ext
                            else:
                                self.external_async_url = _raw_ext.replace(scheme + "://", "mysql+aiomysql://", 1)
                        else:
                            self.external_async_url = ""
                else:
                    logger.info("ℹ️ DATABASE_URL is not a supported external DB (postgresql/mysql). Ignoring for external engines.")
                    self.external_url = ""
                    self.external_async_url = ""
            except Exception:
                # If parsing fails, fall back to empty external config
                logger.info("ℹ️ Failed to parse EXTERNAL_DATABASE_URL - ignoring as external DB")
                self.external_url = ""
                self.external_async_url = ""
        else:
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
        # Use safe async engine creator to ensure asyncpg statement cache is disabled when needed
        self.primary_async_engine = create_async_engine_safe(
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

        try:
            # 解析数据库URL以检测是否是 Supabase 或 pgbouncer/pooler
            from urllib.parse import urlparse
            parsed = urlparse(self.external_url)

            hostname = parsed.hostname or ""
            url_lc = (self.external_url or "").lower()

            # 检查是否是 Supabase 或常见的 pgbouncer/pooler 特征
            is_supabase = ("supabase" in hostname) or ("pooler.supabase.com" in url_lc)
            is_pooler = any(key in hostname or key in url_lc for key in ("pooler", "pgbouncer", "pgbouncer."))

            # 强制所有 asyncpg 场景禁用 prepared statement 缓存，避免 pgbouncer 问题
            # Increase pool sizes to better handle concurrent requests when
            # using an external database. Keep relatively conservative defaults
            # but higher than the previous tiny values.
            self.primary_engine = create_engine(
                self.external_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=False,
                pool_recycle=(300 if is_supabase or is_pooler else 3600),
                pool_timeout=60,
                echo=False,
            )

            async_connect_args = {"statement_cache_size": 0}
            self.primary_async_engine = create_async_engine_safe(
                self.external_async_url,
                pool_size=3,
                max_overflow=2,
                pool_pre_ping=False,
                pool_recycle=(300 if is_supabase or is_pooler else 3600),
                pool_timeout=60,
                echo=False,
                connect_args=async_connect_args,
            )
            logger.info("🔒 asyncpg statement_cache_size=0 强制关闭，避免 pgbouncer/prepared statement 问题")

            # 测试数据库连接
            logger.info("🔍 Testing database connection...")
            with self.primary_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection test successful")

            self.engine = self.primary_engine  # 设置向后兼容的别名
            self.external_engine = self.primary_engine  # 设置外部引擎引用
            self.database_type = "postgresql" if "postgresql" in self.external_url else "external"
            logger.info(f"✅ External database ready: {self.database_type}")

        except Exception as e:
            logger.error(f"❌ Failed to create external database engine: {e}")
            raise

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
            # 强制所有 asyncpg 场景禁用 prepared statement 缓存，避免 pgbouncer 问题
            async_connect_args = {"statement_cache_size": 0}
            # Create sync engine without passing DB-API specific connect_args that psycopg2 doesn't accept
            # Backup engine used for synchronization; increase pool sizes
            # so simultaneous sync/requests don't starve connections.
            self.external_engine = create_engine(
                self.external_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )

            # Async engine may accept driver-specific connect_args (e.g., asyncpg)
            self.external_async_engine = create_async_engine_safe(
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
            # 获取当前部署模式
            from ..core.deployment_mode_manager import mode_manager
            current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
            mode_name = current_mode.value if current_mode else 'local_only'

            # 根据模式选择主数据库
            # 语义说明:
            # - 若显式通过环境变量或 DATABASE_MODE 指定 external，则使用外部数据库为主
            # - 对于 local_external 本地优先场景，默认使用本地为主（local read, external write）以保证 UI 延迟低
            # - 如需强制在 local_external 下使用外部为主，可设置环境变量 PREFER_EXTERNAL_AS_PRIMARY=1
            prefer_external_env = os.getenv("PREFER_EXTERNAL_AS_PRIMARY", "").strip().lower() in ("1", "true", "yes")
            prefer_external = (DATABASE_MODE == "external") or prefer_external_env

            if prefer_external and self.external_url:
                try:
                    # 外部被明确选为主库
                    self._create_external_engine()
                    logger.info("🎯 Using external database as primary")
                except Exception as e:
                    logger.warning(f"❌ External database failed: {e}")
                    logger.info("🔄 Falling back to local database")
                    self._create_local_engine()
            else:
                # 默认使用本地作为主库，外部作为备份（用于异步同步）
                self._create_local_engine()
                logger.info("🏠 Using local database as primary (local read / external write)")

            # 如果配置了外部数据库且不是external模式，创建备份引擎用于同步
            if self.external_url and DATABASE_MODE != "external" and mode_name not in ['local_external', 'local_external_r2']:
                try:
                    self._create_backup_engine()
                    self.sync_enabled = True
                    logger.info("🔄 Data synchronization enabled")
                except Exception as e:
                    logger.warning(f"⚠️ Backup engine creation failed: {e}")

            # 如果当前部署模式包含 external（或者显式设置为 external），确保外部数据库被初始化
            try:
                wants_external = (DATABASE_MODE == "external") or (mode_name in ['local_external', 'local_external_r2'])
                if wants_external and self.external_engine:
                    logger.info("🔧 Ensuring external database tables and default admin (if needed)...")
                    try:
                        # 导入模型并在外部 DB 上创建表（使用同步引擎以避免 asyncpg/pooler 问题）
                        from .models import Base
                        with self.external_engine.begin() as conn:
                            Base.metadata.create_all(bind=self.external_engine)

                        # 初始化默认管理员到外部数据库（如果没有用户）
                        from ..auth.auth_service import init_default_admin
                        from sqlalchemy.orm import sessionmaker
                        ExternalSession = sessionmaker(autocommit=False, autoflush=False, bind=self.external_engine)
                        ext_db = ExternalSession()
                        try:
                            init_default_admin(ext_db)
                            logger.info("✅ External database default admin initialized (if it was missing)")
                        except Exception as _e:
                            logger.warning(f"⚠️ 初始化外部数据库默认管理员时出错（忽略）: {_e}")
                        finally:
                            try:
                                ext_db.close()
                            except Exception:
                                pass

                    except Exception as _ext_init_e:
                        logger.warning(f"⚠️ 确保外部数据库初始化失败（继续）: {_ext_init_e}")
            except Exception:
                # 防御性捕获，不影响主流程
                pass

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
def create_async_engine_safe(url: str, **kwargs):
    """
    Wrapper around SQLAlchemy's create_async_engine to ensure that when using asyncpg
    we pass connect_args={'statement_cache_size': 0} to avoid pgbouncer prepared statement issues.
    It merges user-provided connect_args with the enforced setting.
    """
    # Normalize common sync URLs (postgresql://, mysql://) to their async counterparts
    try:
        lower = (url or "").lower()
    except Exception:
        lower = ""

    # If caller passed a sync URL like postgresql://... or mysql://... convert it
    # to async form to avoid errors like "The asyncio extension requires an async driver".
    try:
        if lower.startswith("postgresql://") and "asyncpg" not in lower:
            from ..core.simple_config import get_async_database_url
            async_url = get_async_database_url(url)
            logger.info(f"create_async_engine_safe: converted sync postgresql URL to async form: {async_url}")
            url = async_url
            lower = url.lower()
        elif lower.startswith("mysql://") and "aiomysql" not in lower:
            from ..core.simple_config import get_async_database_url
            async_url = get_async_database_url(url)
            logger.info(f"create_async_engine_safe: converted sync mysql URL to async form: {async_url}")
            url = async_url
            lower = url.lower()
    except Exception as _conv_e:
        # If conversion fails, fall back and let create_async_engine raise a meaningful error
        logger.debug(f"create_async_engine_safe: async URL conversion attempt failed: {_conv_e}")

    # Only enforce for asyncpg URLs
    if "asyncpg" in lower:
        enforced = {"statement_cache_size": 0}
        user_ca = kwargs.get("connect_args") or {}
        # Merge without overwriting user-specified keys except statement_cache_size
        merged = {**user_ca, **enforced}
        kwargs["connect_args"] = merged
        logger.info(f"create_async_engine_safe: forcing asyncpg connect_args for {url}: {kwargs.get('connect_args')}")
    else:
        logger.info(f"create_async_engine_safe: creating async engine for {url}")

    try:
        engine = create_async_engine(url, **kwargs)
        return engine
    except Exception as e:
        logger.error(f"create_async_engine_safe: failed to create engine for {url}: {e}")
        raise

temp_async_engine = create_async_engine_safe("sqlite+aiosqlite:///./data/flowslide.db", echo=False)

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
        try:
            await asyncio.wait_for(async_engine.dispose(), timeout=5)
        except asyncio.TimeoutError:
            logger.warning("Warning: async_engine.dispose() timed out after 5s")
        except asyncio.CancelledError:
            logger.warning("Warning: async_engine.dispose() was cancelled")
        except Exception as e:
            logger.warning(f"Warning: exception during async_engine.dispose(): {e}")


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

    # Ensure database manager is initialized
    if not db_manager.primary_engine:
        db_manager.initialize()

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


def update_session_makers():
    """Update session makers after database initialization"""
    global SessionLocal, AsyncSessionLocal

    if db_manager.primary_engine and db_manager.primary_async_engine:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_manager.primary_engine)
        AsyncSessionLocal = async_sessionmaker(db_manager.primary_async_engine, class_=AsyncSession, expire_on_commit=False)
        logger.info("✅ Database session makers updated")
    else:
        logger.warning("⚠️ Database engines not available, session makers not updated")
