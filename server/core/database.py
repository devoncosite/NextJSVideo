"""PostgreSQL Database Connection & SQLAlchemy 2.0 Async Session (TASK-1.1)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from server.core.config import Settings, get_settings


def build_engine_kwargs(database_url: str, settings: Settings) -> Dict[str, Any]:
    """Build SQLAlchemy create_async_engine parameters with connection pool settings."""
    if database_url.startswith("sqlite"):
        return {
            "echo": False,
            "poolclass": NullPool,
        }
    return {
        "echo": False,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    }


def create_db_engine(database_url: str | None = None) -> AsyncEngine:
    """Create configured SQLAlchemy 2.0 AsyncEngine."""
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    kwargs = build_engine_kwargs(url, settings)
    return create_async_engine(url, **kwargs)


engine: AsyncEngine = create_db_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI async session dependency with automatic rollback on unhandled exceptions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health(custom_engine: AsyncEngine | None = None) -> bool:
    """Execute SELECT 1 against the configured async engine."""
    target_engine = custom_engine or engine
    async with target_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return result.scalar_one() == 1
