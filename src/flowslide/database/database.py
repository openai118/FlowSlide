"""
Database configuration and session management
"""

import os
import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ..core.simple_config import app_config, DATABASE_URL, ASYNC_DATABASE_URL

logger = logging.getLogger(__name__)

# Database fallback configuration
def get_safe_database_urls():
    """Get database URLs with fallback to SQLite if PostgreSQL fails"""
    primary_db_url = DATABASE_URL
    primary_async_url = ASYNC_DATABASE_URL
    
    # SQLite fallback
    fallback_db_url = "sqlite:///./data/flowslide.db"
    fallback_async_url = "sqlite+aiosqlite:///./data/flowslide.db"
    
    # If PostgreSQL URL is provided but we're in a container/cloud environment
    # where the PostgreSQL server might not be available, prepare fallback
    if primary_db_url.startswith("postgresql://"):
        logger.info(f"Primary database: PostgreSQL")
        logger.info(f"Fallback database: SQLite")
        return (primary_db_url, primary_async_url, fallback_db_url, fallback_async_url)
    else:
        logger.info(f"Using SQLite database: {primary_db_url}")
        return (primary_db_url, primary_async_url, None, None)

# Get database URLs
primary_url, primary_async_url, fallback_url, fallback_async_url = get_safe_database_urls()

# Create engines with error handling
try:
    # Try primary database first
    if "sqlite" in primary_url:
        # SQLite configuration
        engine = create_engine(
            primary_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        async_engine = create_async_engine(
            primary_async_url,
            echo=False
        )
    else:
        # PostgreSQL configuration with connection pooling
        engine = create_engine(
            primary_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
        async_engine = create_async_engine(
            primary_async_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
    
    # Test connection for PostgreSQL
    if primary_url.startswith("postgresql://"):
        try:
            # Quick connection test
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            logger.info("✅ PostgreSQL connection successful")
            DATABASE_TYPE = "postgresql"
        except Exception as e:
            logger.warning(f"❌ PostgreSQL connection failed: {e}")
            if fallback_url and fallback_async_url:
                logger.info("🔄 Falling back to SQLite...")
                engine = create_engine(
                    fallback_url,
                    connect_args={"check_same_thread": False},
                    echo=False,
                )
                async_engine = create_async_engine(
                    fallback_async_url,
                    echo=False
                )
                DATABASE_TYPE = "sqlite"
                logger.info("✅ SQLite fallback successful")
            else:
                raise
    else:
        DATABASE_TYPE = "sqlite"
        logger.info("✅ SQLite database ready")
        
except Exception as e:
    logger.error(f"❌ Database initialization failed: {e}")
    # Final fallback to SQLite
    logger.info("🔄 Using final SQLite fallback...")
    engine = create_engine(
        "sqlite:///./data/flowslide.db",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async_engine = create_async_engine("sqlite+aiosqlite:///./data/flowslide.db", echo=False)
    DATABASE_TYPE = "sqlite"
    logger.info("✅ Final SQLite fallback ready")

# Create session makers
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """Dependency to get async database session"""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Initialize database tables with error handling"""
    try:
        # Import here to avoid circular imports
        from .models import Base

        logger.info(f"🗄️ Initializing database tables using {DATABASE_TYPE}...")
        
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
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Try to handle the error gracefully
        if "postgresql" in str(e).lower() or "asyncpg" in str(e).lower():
            logger.error("💡 Hint: This appears to be a PostgreSQL connection issue.")
            logger.error("   Consider checking your DATABASE_URL or using SQLite as fallback.")
        raise


async def close_db():
    """Close database connections"""
    await async_engine.dispose()
