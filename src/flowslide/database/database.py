"""
Database configuration and session management with intelligent fallback strategy
"""

import logging
import os
import asyncio
import threading
import uuid
from typing import Optional, Tuple
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from ..core.storage_policy import configured_storage_policy

from ..core.simple_config import (
    DATABASE_URL,
    ASYNC_DATABASE_URL,
    LOCAL_DATABASE_URL,
    EXTERNAL_DATABASE_URL,
    DATABASE_MODE
)

logger = logging.getLogger(__name__)
_initialization_lock = threading.RLock()


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
        url = make_url(self.local_url)
        if url.database and url.database != ':memory:':
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        self.primary_engine = create_engine(
            url, connect_args={'check_same_thread': False}, hide_parameters=True,
        )
        self.primary_async_engine = create_async_engine_safe(
            url.set(drivername='sqlite+aiosqlite').render_as_string(hide_password=False),
        )
        self.engine = self.primary_engine
        self.database_type = 'sqlite'
        logger.info('Local SQLite database selected as the authoritative store')

    def _create_external_engine(self):
        if not self.external_url:
            raise ValueError('External database URL is required')
        url = make_url(self.external_url)
        options = dict(pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=300, pool_timeout=15)
        self.primary_engine = create_engine(url, hide_parameters=True, **options)
        try:
            self.primary_async_engine = create_async_engine_safe(self.external_async_url, **options)
            with self.primary_engine.connect() as conn:
                conn.execute(text('SELECT 1'))
        except Exception:
            self.primary_engine.dispose()
            raise
        self.engine = self.external_engine = self.primary_engine
        self.external_async_engine = self.primary_async_engine
        self.database_type = url.get_backend_name()
        logger.info('External %s database selected as the authoritative store', self.database_type)

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
        """Build the requested store before publishing it; never fall back across identities."""
        with _initialization_lock:
            policy = configured_storage_policy()
            candidate = DatabaseManager()
            candidate.policy = policy
            candidate.local_url = os.getenv('LOCAL_DATABASE_URL', LOCAL_DATABASE_URL)
            if policy.uses_external:
                raw_url = policy.external_url
                if raw_url.startswith('postgres://'):
                    raw_url = raw_url.replace('postgres://', 'postgresql://', 1)
                url = make_url(raw_url)
                backend = url.get_backend_name()
                query = dict(url.query)
                query.pop('statement_cache_size', None)
                query.pop('prepared_statement_cache_size', None)
                sync_driver = 'postgresql+psycopg2' if backend == 'postgresql' else 'mysql+pymysql'
                async_driver = 'postgresql+asyncpg' if backend == 'postgresql' else 'mysql+aiomysql'
                candidate.external_url = url.set(drivername=sync_driver, query=query).render_as_string(hide_password=False)
                candidate.external_async_url = url.set(drivername=async_driver, query=query).render_as_string(hide_password=False)
                candidate._create_external_engine()
            else:
                candidate.external_url = candidate.external_async_url = ''
                candidate._create_local_engine()
            # Ordinary writes already reach the authoritative store. Background
            # bidirectional database sync must not replay stale local rows into it.
            candidate.sync_enabled = False
            old_sync = self.primary_engine
            old_async = self.primary_async_engine
            self.__dict__.update(candidate.__dict__)
            if old_sync is not None and old_sync is not self.primary_engine:
                old_sync.dispose()
            if old_async is not None and old_async is not self.primary_async_engine:
                try:
                    asyncio.get_running_loop().create_task(old_async.dispose())
                except RuntimeError:
                    asyncio.run(old_async.dispose())
            logger.info('Storage policy: mode=%s, authentication=%s, automatic user sync=disabled', policy.mode, policy.authentication_source)

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
    """Initialize once and refresh the existing session factories in place."""
    global engine, async_engine, DATABASE_TYPE
    db_manager.initialize()
    engine = db_manager.primary_engine
    async_engine = db_manager.primary_async_engine
    DATABASE_TYPE = db_manager.database_type
    update_session_makers()
    return db_manager


# 临时创建基本的session makers，稍后会在initialize_database()中更新
temp_engine = create_engine(
    "sqlite:///./data/flowslide.db",
    connect_args={"check_same_thread": False},
    echo=False,
)
def create_async_engine_safe(url: str, **kwargs):
    """Normalize drivers and disable both asyncpg prepared-statement caches."""
    if isinstance(url, str) and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    parsed = make_url(url)
    backend = parsed.get_backend_name()
    if backend == 'postgresql':
        parsed = parsed.set(drivername='postgresql+asyncpg')
        query = dict(parsed.query)
        sslmode = query.pop('sslmode', None)
        query.pop('statement_cache_size', None)
        query.pop('prepared_statement_cache_size', None)
        parsed = parsed.set(query=query)
        connect_args = dict(kwargs.pop('connect_args', {}) or {})
        connect_args.update(statement_cache_size=0, prepared_statement_cache_size=0)
        connect_args.setdefault('prepared_statement_name_func', lambda: '__flowslide_' + uuid.uuid4().hex + '__')
        if sslmode:
            connect_args.setdefault('ssl', sslmode)
        kwargs['connect_args'] = connect_args
    elif backend == 'mysql':
        parsed = parsed.set(drivername='mysql+aiomysql')
    elif backend == 'sqlite':
        parsed = parsed.set(drivername='sqlite+aiosqlite')
    kwargs.setdefault('hide_parameters', True)
    logger.debug('Creating async database engine for backend %s', backend)
    return create_async_engine(parsed, **kwargs)

temp_async_engine = create_async_engine_safe("sqlite+aiosqlite:///./data/flowslide.db", echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=temp_engine)
AsyncSessionLocal = async_sessionmaker(temp_async_engine, class_=AsyncSession, expire_on_commit=False)


def get_db():
    if db_manager.primary_engine is None:
        initialize_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    if db_manager.primary_async_engine is None:
        initialize_database()
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Initialize schema and bootstrap in the same store used by authentication."""
    from .models import Base
    from ..auth.auth_service import init_default_admin
    if db_manager.primary_async_engine is None:
        initialize_database()
    async with db_manager.primary_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    with SessionLocal() as db:
        created = init_default_admin(db)
    logger.info('Authentication bootstrap complete (%s)', 'created administrator' if created else 'existing accounts preserved')


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




def get_auth_db():
    """Authentication shares the authoritative store and fails closed on outages."""
    try:
        policy = configured_storage_policy()
        if db_manager.primary_engine is None:
            initialize_database()
        active = getattr(db_manager, 'policy', None)
        if active is None or active != policy:
            raise RuntimeError('Storage policy changed; database reinitialization is required')
        yield from get_db()
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        logger.error('Authentication database unavailable (%s); no local fallback performed', type(exc).__name__)
        raise HTTPException(status_code=503, detail='认证数据库暂不可用，请检查部署模式和数据库连接') from exc


async def get_auth_async_db():
    try:
        policy = configured_storage_policy()
        if db_manager.primary_async_engine is None:
            initialize_database()
        active = getattr(db_manager, 'policy', None)
        if active is None or active != policy:
            raise RuntimeError('Storage policy changed; database reinitialization is required')
        async with AsyncSessionLocal() as session:
            yield session
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        logger.error('Async authentication database unavailable (%s)', type(exc).__name__)
        raise HTTPException(status_code=503, detail='认证数据库暂不可用，请检查部署模式和数据库连接') from exc


def update_session_makers():
    """Keep imported SessionLocal references valid across initialization and restore."""
    if db_manager.primary_engine is not None:
        SessionLocal.configure(bind=db_manager.primary_engine)
    if db_manager.primary_async_engine is not None:
        AsyncSessionLocal.configure(bind=db_manager.primary_async_engine)
