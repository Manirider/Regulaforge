"""Database session dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.infrastructure.persistence.database import get_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for request handling."""
    async for session in get_session():
        yield session
