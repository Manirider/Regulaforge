"""SQLAlchemy models for AssessableEntity."""

import uuid
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin, VersionMixin


class AssessableEntityModel(Base, TimestampMixin, VersionMixin):
    """SQLAlchemy model for AssessableEntity."""

    __tablename__ = "assessable_entities"

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_entity_tenant_name"),
        Index("ix_entities_tenant_id", "tenant_id"),
        Index("ix_entities_type", "entity_type"),
        Index("ix_entities_parent", "parent_entity_id"),
        Index("ix_entities_active", "is_active"),
        {
            "comment": "Entities subject to compliance assessment",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Entity identifier"
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Entity name"
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Entity type classification"
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, comment="Owning tenant ID"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Entity description"
    )
    parent_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("assessable_entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent entity in hierarchy",
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Searchable tags"
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="Flexible entity attributes"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether entity is active"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Creator user ID"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Last modifier user ID"
    )

    def __repr__(self) -> str:
        return f"<EntityModel {self.name} [{self.entity_type}]>"
