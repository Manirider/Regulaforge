"""SQLAlchemy model for User aggregate."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin, VersionMixin


class UserModel(Base, TimestampMixin, VersionMixin):
    """SQLAlchemy model for the User aggregate root."""

    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_tenant_id", "tenant_id"),
        Index("ix_users_is_active", "is_active"),
        Index("ix_users_is_superuser", "is_superuser"),
        Index("ix_users_last_login_at", "last_login_at"),
        Index("ix_users_locked_until", "locked_until"),
        {
            "comment": "Platform users with authentication credentials",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Unique user identifier"
    )
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="User email address (used for login)"
    )
    username: Mapped[str] = mapped_column(
        String(150), nullable=False, comment="Unique username"
    )
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="BCrypt password hash"
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="User display name"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether the user account is active"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="System-wide administrator flag"
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        comment="Owning tenant identifier",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Last successful login timestamp (UTC)"
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Consecutive failed login count"
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Account lockout expiration (UTC)"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who created this record"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who last updated this record"
    )

    # Relationships
    roles: Mapped[list["UserRoleModel"]] = relationship(  # noqa: F821
        "UserRoleModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<UserModel {self.username}: {self.email}>"
