"""SQLAlchemy model for Regulation aggregate."""

import uuid
from datetime import date
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin, VersionMixin


class RegulationModel(Base, TimestampMixin, VersionMixin):
    """SQLAlchemy model for the Regulation aggregate."""

    __tablename__ = "regulations"

    __table_args__ = (
        UniqueConstraint("code", name="uq_regulations_code"),
        Index("ix_regulations_status", "status"),
        Index("ix_regulations_category", "category"),
        Index("ix_regulations_jurisdiction", "jurisdiction"),
        Index("ix_regulations_issuing_body", "issuing_body"),
        Index("ix_regulations_effective_date", "effective_date"),
        {
            "comment": "Regulatory documents, laws, standards, and policies",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique regulation identifier",
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Regulation title"
    )
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Unique regulation code (e.g., GDPR)"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Detailed regulation description"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Regulation category"
    )
    jurisdiction: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Applicable jurisdiction"
    )
    issuing_body: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Regulatory body name"
    )
    effective_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Date regulation takes effect"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft", comment="Regulation lifecycle status"
    )
    version_str: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1.0", comment="Regulation version"
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Searchable tags"
    )
    parent_regulation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("regulations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent regulation if this is an amendment",
    )
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("regulations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Regulation that supersedes this one",
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="Flexible metadata"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who created this record"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="User who last updated this record"
    )

    # Relationships
    requirements: Mapped[list["RegulationRequirementModel"]] = relationship(
        "RegulationRequirementModel",
        back_populates="regulation",
        cascade="all, delete-orphan",
        order_by="RegulationRequirementModel.code",
    )

    def __repr__(self) -> str:
        return f"<RegulationModel {self.code}: {self.title[:50]}>"


class RegulationRequirementModel(Base, TimestampMixin):
    """SQLAlchemy model for regulation requirements."""

    __tablename__ = "regulation_requirements"

    __table_args__ = (
        UniqueConstraint("regulation_id", "code", name="uq_req_regulation_code"),
        Index("ix_requirements_regulation_id", "regulation_id"),
        {
            "comment": "Individual requirements within regulations",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Requirement identifier"
    )
    regulation_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("regulations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent regulation",
    )
    code: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Requirement code within regulation"
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Requirement title"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Requirement description"
    )
    parent_requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("regulation_requirements.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent requirement if hierarchical",
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether requirement is mandatory"
    )
    risk_weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, comment="Risk weight (0.0 to 1.0)"
    )
    guidance: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Implementation guidance"
    )
    references: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Reference links"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Display ordering"
    )

    # Relationships
    regulation: Mapped["RegulationModel"] = relationship(
        "RegulationModel", back_populates="requirements"
    )

    def __repr__(self) -> str:
        return f"<RequirementModel {self.code}: {self.title[:40]}>"
