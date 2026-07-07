"""SQLAlchemy model for Tenant aggregate."""

import uuid
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin, VersionMixin


class TenantModel(Base, TimestampMixin, VersionMixin):
    """SQLAlchemy model for the Tenant aggregate root."""

    __tablename__ = "tenants"

    __table_args__ = (
        UniqueConstraint("name", name="uq_tenants_name"),
        UniqueConstraint("slug", name="uq_tenants_slug"),
        Index("ix_tenants_is_active", "is_active"),
        Index("ix_tenants_domain", "domain"),
        {
            "comment": "Organization workspaces that isolate users and data",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Unique tenant identifier"
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Organization name"
    )
    slug: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="URL-friendly unique identifier"
    )
    domain: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Organization domain for SSO/email matching"
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="Tenant-specific configuration"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether the tenant is active"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who created this tenant"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who last updated this tenant"
    )

    def __repr__(self) -> str:
        return f"<TenantModel {self.name} ({self.slug})>"
