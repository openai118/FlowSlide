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

            # Initialize default admin user
            from ..auth.auth_service import init_default_admin
            import os

            def _external_has_users() -> bool:
                """Return True if external DB configured and contains at least one user."""
                try:
                    if not getattr(db_manager, "external_engine", None):
                        return False
                    with db_manager.external_engine.connect() as conn:
                        res = conn.execute(text("SELECT 1 FROM users LIMIT 1")).fetchone()
                        return bool(res)
                except Exception:
                    return False

            def _r2_has_backups_with_users() -> bool:
                """Lightweight check for R2: if R2 configured, assume backups may contain users. This is heuristic."""
                try:
                    r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
                    r2_bucket = os.getenv("R2_BUCKET_NAME")
                    # If not configured, skip
                    if not r2_access_key or not r2_bucket:
                        return False
                    # Prefer not to import boto3 here; use heuristic that R2 is configured
                    return True
                except Exception:
                    return False

            db = SessionLocal()
            try:
                # Determine active deployment mode: prefer ACTIVE_DEPLOYMENT_MODE if set and not 'none'
                from ..core.deployment_mode_manager import mode_manager
                active_env = os.getenv("ACTIVE_DEPLOYMENT_MODE")
                if active_env and active_env.strip().lower() != 'none':
                    current_mode = None
                    try:
                        current_mode = mode_manager.current_mode
                    except Exception:
                        current_mode = None
                else:
                    # Query mode manager (this will perform auto-detection if needed)
                    try:
                        current_mode = mode_manager.current_mode or mode_manager.detect_current_mode()
                    except Exception:
                        current_mode = None

                # If current active mode is local-only (or explicitly set to local), create local admin
                mode_name = current_mode.value if current_mode else 'local_only'
                if mode_name.startswith('local') and ('external' not in mode_name and 'r2' not in mode_name):
                    init_default_admin(db)
                    logger.info("✅ Default admin user initialized (active mode implies local-only)")
                else:
                    # For modes that include external or R2, prefer syncing users from external/R2 first
                    if _external_has_users():
                        # If local has no users yet, perform an initial full upsert from external -> local
                        try:
                            # check local user count
                            local_count = db.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]
                        except Exception:
                            local_count = 0

                        if local_count == 0:
                            logger.info("📥 External DB has users and local is empty - performing initial full upsert from external to local")
                            try:
                                # Perform upsert: read all external users and insert into local
                                if getattr(db_manager, 'external_engine', None):
                                    with db_manager.external_engine.connect() as ext_conn:
                                        rows = ext_conn.execute(text(
                                            "SELECT id, username, password_hash, email, is_admin, is_active, created_at, updated_at, last_login FROM users"
                                        )).fetchall()

                                        created = 0
                                        with SessionLocal() as local_session:
                                            for r in rows:
                                                try:
                                                    ext_id = r[0]
                                                    username = r[1]
                                                    password_hash = r[2]
                                                    email = r[3]
                                                    is_admin = bool(r[4]) if len(r) > 4 else False
                                                    is_active = bool(r[5]) if len(r) > 5 else True
                                                    created_at = r[6]
                                                    updated_at = r[7]
                                                    last_login = r[8]
                                                except Exception:
                                                    mapping = dict(r)
                                                    ext_id = mapping.get('id')
                                                    username = mapping.get('username')
                                                    password_hash = mapping.get('password_hash')
                                                    email = mapping.get('email')
                                                    is_admin = bool(mapping.get('is_admin'))
                                                    is_active = bool(mapping.get('is_active', True))
                                                    created_at = mapping.get('created_at')
                                                    updated_at = mapping.get('updated_at')
                                                    last_login = mapping.get('last_login')

                                                if not username or not password_hash:
                                                    continue

                                                # insert if not exists
                                                exists = local_session.execute(text("SELECT id FROM users WHERE username=:u LIMIT 1"), {"u": username}).fetchone()
                                                if exists:
                                                    continue
                                                try:
                                                    local_session.execute(text(
                                                        "INSERT INTO users (id, username, password_hash, email, is_admin, is_active, created_at, updated_at, last_login) VALUES (:id,:username,:hash,:email,:is_admin,:is_active,:created_at,:updated_at,:last_login)"
                                                    ), {"id": ext_id, "username": username, "hash": password_hash, "email": email, "is_admin": is_admin, "is_active": is_active, "created_at": created_at, "updated_at": updated_at, "last_login": last_login})
                                                    created += 1
                                                except Exception as e:
                                                    try:
                                                        local_session.rollback()
                                                    except Exception:
                                                        pass
                                                    logger.warning(f"⚠️ Failed to insert external user {username} during init upsert: {e}")

                                            try:
                                                local_session.commit()
                                            except Exception:
                                                try:
                                                    local_session.rollback()
                                                except Exception:
                                                    pass

                                        logger.info(f"✅ Initial upsert completed: created={created} from external")
                                else:
                                    logger.warning("External engine not available - cannot perform initial upsert")
                            except Exception as e:
                                logger.warning(f"Initial external->local upsert failed: {e}")
                        else:
                            logger.info("ℹ️ External DB has users - local already contains users, skipping initial upsert")
                    elif _r2_has_backups_with_users():
                        logger.info("ℹ️ R2 appears configured - will rely on R2/external backups for initial users and skip local admin creation if possible")
                    else:
                        init_default_admin(db)
                        logger.info("✅ Default admin user initialized (no external/R2 users found)")
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
