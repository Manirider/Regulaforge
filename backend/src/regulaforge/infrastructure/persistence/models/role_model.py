"""SQLAlchemy models for Role aggregate and UserRole junction."""

import uuid
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin, VersionMixin


class RoleModel(Base, TimestampMixin, VersionMixin):
    """SQLAlchemy model for Role."""

    __tablename__ = "roles"

    __table_args__ = (
        UniqueConstraint("name", name="uq_roles_name"),
        Index("ix_roles_is_system_role", "is_system_role"),
        {
            "comment": "RBAC roles with associated permissions",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Unique role identifier"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Unique role name"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Role description and purpose"
    )
    permissions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="List of permission strings granted by this role"
    )
    is_system_role: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="System-defined roles are immutable"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who created this role"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who last updated this role"
    )

    # Relationships
    user_assignments: Mapped[list["UserRoleModel"]] = relationship(
        "UserRoleModel",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RoleModel {self.name}>"


class UserRoleModel(Base, TimestampMixin):
    """Junction table linking users to roles with optional tenant scope."""

    __tablename__ = "user_roles"

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "tenant_id", name="uq_user_role_tenant"),
        Index("ix_user_roles_user_id", "user_id"),
        Index("ix_user_roles_role_id", "role_id"),
        Index("ix_user_roles_tenant_id", "tenant_id"),
        {
            "comment": "Many-to-many relationship between users and roles",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Assignment identifier"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User receiving the role",
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        comment="Role being assigned",
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        comment="Tenant scope (None for global roles)",
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(  # noqa: F821
        "UserModel", back_populates="roles"
    )
    role: Mapped["RoleModel"] = relationship(
        "RoleModel", back_populates="user_assignments"
    )

    def __repr__(self) -> str:
        return f"<UserRoleModel user={self.user_id} role={self.role_id}>"
