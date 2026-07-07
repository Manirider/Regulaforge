"""Base SQLAlchemy model with common columns."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, TypeDecorator, func, types
from sqlalchemy.orm import Mapped, mapped_column


class GUID(TypeDecorator):
    """Platform-independent GUID type for SQLAlchemy.

    Uses PostgreSQL UUID type natively, falls back to CHAR(32) for others.
    """
    impl = types.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(types.UUID())
        return dialect.type_descriptor(types.String(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value).replace("-", "")

    def process_result_value(self, value, _dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class TimestampMixin:
    """Mixin adding created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="Record last update timestamp (UTC)",
    )


class VersionMixin:
    """Mixin adding optimistic concurrency version column."""

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Optimistic concurrency version",
    )
