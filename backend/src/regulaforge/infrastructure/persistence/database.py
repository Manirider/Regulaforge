"""Database engine and session management.

Configures SQLAlchemy async engine and session factory for
PostgreSQL with proper connection pooling, retry logic, and
health checks.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    __abstract__ = True


_engine = None
_session_factory = None


async def initialize_database() -> None:
    """Initialize the database engine and connection pool.

    Must be called once at application startup.
    """
    global _engine, _session_factory

    if _engine is not None:
        logger.warning("Database already initialized")
        return

    db_url = str(settings.database.url)
    pool_size = settings.database.pool_size
    pool_recycle = settings.database.pool_recycle

    logger.info(
        "Initializing database connection pool: pool_size=%d, recycle=%ds",
        pool_size, pool_recycle,
    )

    engine_kwargs = {
        "pool_size": pool_size,
        "max_overflow": settings.database.max_overflow,
        "pool_recycle": pool_recycle,
        "pool_pre_ping": True,
        "echo": settings.database.echo,
    }

    # Use NullPool for serverless environments
    if settings.is_production():
        engine_kwargs["poolclass"] = NullPool

    _engine = create_async_engine(db_url, **engine_kwargs)

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    logger.info("Database initialized successfully")


async def shutdown_database() -> None:
    """Dispose of the database engine and connection pool.

    Must be called at application shutdown.
    """
    global _engine, _session_factory

    if _engine:
        logger.info("Shutting down database connection pool")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection pool disposed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with automatic cleanup.

    Yields:
        An async SQLAlchemy session.

    Raises:
        RuntimeError: If database not initialized.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call initialize_database() first."
        )

    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def transaction_session() -> AsyncIterator[AsyncSession]:
    """Context manager for manual transaction control.

    Use when you need explicit control over commit/rollback.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call initialize_database() first."
        )

    session = _session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_database_health() -> bool:
    """Check if the database is reachable and healthy.

    Returns:
        True if the database responds to a simple query.
    """
    if not _engine:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False
