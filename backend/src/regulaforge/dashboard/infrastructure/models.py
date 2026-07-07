"""SQLAlchemy models for the Enterprise Dashboard.

Provides database models for dashboard configurations, compliance
snapshots, and activity records with proper indexes, constraints,
and JSON column types for flexible data storage.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin, VersionMixin


class DashboardConfigModel(Base, TimestampMixin, VersionMixin):
    """SQLAlchemy model for dashboard configurations.

    Stores tenant-specific dashboard layouts, widget configurations,
    and sharing settings.
    """

    __tablename__ = "dashboard_configs"

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dashboard_config_tenant_name"),
        Index("ix_dashboard_config_tenant_id", "tenant_id"),
        Index("ix_dashboard_config_is_default", "is_default"),
        {
            "comment": "Tenant dashboard layout configurations",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        comment="Dashboard configuration identifier",
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Configuration name",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Configuration description",
    )
    layout: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Widget layout definitions",
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False,
        comment="Owning tenant ID",
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True,
        comment="Creating user ID",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Whether this is the default dashboard",
    )
    sharing_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict,
        comment="Dashboard sharing and visibility settings",
    )

    def __repr__(self) -> str:
        return f"<DashboardConfigModel {self.name} tenant={self.tenant_id}>"


class ComplianceSnapshotModel(Base, TimestampMixin):
    """SQLAlchemy model for compliance snapshots.

    Stores point-in-time compliance posture data for historical
    trend analysis and comparison.
    """

    __tablename__ = "compliance_snapshots"

    __table_args__ = (
        Index("ix_compliance_snapshots_tenant_id", "tenant_id"),
        Index("ix_compliance_snapshots_timestamp", "timestamp"),
        Index("ix_compliance_snapshots_tenant_ts", "tenant_id", "timestamp"),
        {
            "comment": "Point-in-time compliance posture snapshots",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        comment="Snapshot identifier",
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False,
        comment="Owning tenant ID",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="When the snapshot was captured",
    )
    overall_compliance_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Overall compliance rate percentage",
    )
    entities_assessed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of assessed entities",
    )
    entities_in_scope: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Total entities in compliance scope",
    )
    findings_by_severity: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict,
        comment="Findings count grouped by severity level",
    )
    overdue_assessments: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of overdue assessments",
    )
    regulations_tracked: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of regulations being tracked",
    )
    active_alerts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of currently active alerts",
    )
    risk_distribution: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict,
        comment="Entity count grouped by risk level",
    )
    top_risk_factors: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Top risk factor descriptions",
    )
    recent_changes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Notable recent changes",
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceSnapshotModel tenant={self.tenant_id} "
            f" rate={self.overall_compliance_rate:.1f}% "
            f" at={self.timestamp.isoformat()}>"
        )


class DashboardActivityModel(Base, TimestampMixin):
    """SQLAlchemy model for dashboard activity feed entries.

    Records all notable activities across the platform for
    display in the dashboard activity feed and audit trails.
    """

    __tablename__ = "dashboard_activity"

    __table_args__ = (
        Index("ix_dashboard_activity_tenant_id", "tenant_id"),
        Index("ix_dashboard_activity_timestamp", "timestamp"),
        Index("ix_dashboard_activity_type", "activity_type"),
        Index("ix_dashboard_activity_severity", "severity"),
        Index("ix_dashboard_activity_user_id", "user_id"),
        Index("ix_dashboard_activity_entity_id", "entity_id"),
        Index("ix_dashboard_activity_tenant_ts", "tenant_id", "timestamp"),
        {
            "comment": "Dashboard activity feed entries",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        comment="Activity entry identifier",
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False,
        comment="Owning tenant ID",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="When the activity occurred",
    )
    activity_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Activity type/category",
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Human-readable activity description",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True,
        comment="User who performed the activity",
    )
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Related entity identifier",
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="info",
        comment="Severity level (info, warning, critical)",
    )
    metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict,
        comment="Additional structured activity data",
    )

    def __repr__(self) -> str:
        return (
            f"<DashboardActivityModel {self.activity_type} "
            f"[{self.severity}] at {self.timestamp.isoformat()}>"
        )
