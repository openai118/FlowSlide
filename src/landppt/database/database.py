"""
Database configuration and session management
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ..core.simple_config import app_config, DATABASE_URL, ASYNC_DATABASE_URL

# Create engines
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,  # Disable SQL logging to reduce noise
)

async_engine = create_async_engine(
    ASYNC_DATABASE_URL, echo=False  # Disable SQL logging to reduce noise
)

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
    """Initialize database tables"""
    # Import here to avoid circular imports
    from .models import Base

    async with async_engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    # Initialize default admin user
    from ..auth.auth_service import init_default_admin

    db = SessionLocal()
    try:
        init_default_admin(db)
    finally:
        db.close()


async def close_db():
    """Close database connections"""
    await async_engine.dispose()
