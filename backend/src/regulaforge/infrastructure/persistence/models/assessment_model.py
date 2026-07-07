"""SQLAlchemy models for Compliance Assessment aggregate."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin, VersionMixin


class ComplianceAssessmentModel(Base, TimestampMixin, VersionMixin):
    """SQLAlchemy model for ComplianceAssessment aggregate."""

    __tablename__ = "compliance_assessments"

    __table_args__ = (
        Index("ix_assessments_entity_id", "entity_id"),
        Index("ix_assessments_status", "status"),
        Index("ix_assessments_assessor", "assessor_id"),
        Index("ix_assessments_due_date", "due_date"),
        Index("ix_assessments_entity_status", "entity_id", "status"),
        {
            "comment": "Compliance assessments evaluating entities against regulations",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Assessment identifier"
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Assessment title"
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, index=True, comment="Assessed entity ID"
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Type of assessed entity"
    )
    assessor_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, comment="Assessor user ID"
    )
    due_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Assessment due date"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="scheduled", comment="Assessment status"
    )
    scope_description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Assessment scope"
    )
    overall_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Final compliance score (0-100)"
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Reviewer who approved"
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Approval timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Completion timestamp"
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="Flexible metadata"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Creator user ID"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Last modifier user ID"
    )

    # Relationships
    findings: Mapped[list["ComplianceFindingModel"]] = relationship(
        "ComplianceFindingModel",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="ComplianceFindingModel.created_at",
    )
    regulation_links: Mapped[list["AssessmentRegulationModel"]] = relationship(
        "AssessmentRegulationModel",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AssessmentModel {self.title[:40]} [{self.status}]>"


class ComplianceFindingModel(Base, TimestampMixin):
    """SQLAlchemy model for compliance findings."""

    __tablename__ = "compliance_findings"

    __table_args__ = (
        Index("ix_findings_assessment_id", "assessment_id"),
        Index("ix_findings_risk_level", "risk_level"),
        Index("ix_findings_status", "status"),
        Index("ix_findings_assigned_to", "assigned_to"),
        {
            "comment": "Findings identified during compliance assessments",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Finding identifier"
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("compliance_assessments.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent assessment",
    )
    requirement_code: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Related requirement code"
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Finding title"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Detailed finding description"
    )
    risk_level: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Risk severity level"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="open", comment="Finding status"
    )
    impact_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Impact score (0-10)"
    )
    likelihood_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Likelihood score (0-10)"
    )
    remediation_recommendation: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Suggested remediation"
    )
    remediation_due_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="Remediation deadline"
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Remediation assignee"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Finding category"
    )
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list, comment="Evidence artifacts"
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Resolution timestamp"
    )

    # Relationships
    assessment: Mapped["ComplianceAssessmentModel"] = relationship(
        "ComplianceAssessmentModel", back_populates="findings"
    )

    def __repr__(self) -> str:
        return f"<FindingModel {self.title[:40]} [{self.risk_level}]>"


class AssessmentRegulationModel(Base, TimestampMixin):
    """Junction table linking assessments to regulations."""

    __tablename__ = "assessment_regulations"

    __table_args__ = (
        UniqueConstraint("assessment_id", "regulation_id", name="uq_assessment_regulation"),
        Index("ix_assessment_regs_regulation", "regulation_id"),
        {
            "comment": "Many-to-many link between assessments and regulations",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("compliance_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    regulation_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("regulations.id", ondelete="CASCADE"),
        nullable=False,
    )

    assessment: Mapped["ComplianceAssessmentModel"] = relationship(
        "ComplianceAssessmentModel", back_populates="regulation_links"
    )

