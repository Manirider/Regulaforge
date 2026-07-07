"""SQLAlchemy ORM model for the audit_logs table.

Provides persistent storage for audit trail entries with
proper indexing for common query patterns.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON as SA_JSON
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID


class AuditLogModel(Base):
    """ORM model for the audit_logs table.

    Stores immutable audit records with indexes on commonly
    queried columns for efficient search and filtering.
    """

    __tablename__ = "audit_logs"

    id: Mapped[GUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
        comment="Unique audit entry identifier",
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="The auditable action performed",
    )
    actor_id: Mapped[GUID] = mapped_column(
        GUID,
        nullable=False,
        index=True,
        comment="UUID of the user who performed the action",
    )
    actor_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        comment="Email of the acting user",
    )
    tenant_id: Mapped[GUID] = mapped_column(
        GUID,
        nullable=False,
        index=True,
        comment="Tenant context UUID",
    )
    resource_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Type of resource affected (e.g. regulation)",
    )
    resource_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Identifier of the specific resource",
    )
    details: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=dict,
        comment="Free-form details about the action",
    )
    changes: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=dict,
        comment="Old/new value pairs for change tracking",
    )
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=True,
        comment="Source IP address (supports IPv6)",
    )
    user_agent: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="User agent string from the request",
    )
    correlation_id: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        comment="Distributed tracing correlation ID",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="When the action occurred (UTC)",
    )

    __table_args__ = (
        Index(
            "ix_audit_logs_resource_type_resource_id",
            "resource_type",
            "resource_id",
        ),
        Index(
            "ix_audit_logs_tenant_id_timestamp",
            "tenant_id",
            "timestamp",
        ),
        Index(
            "ix_audit_logs_actor_id_timestamp",
            "actor_id",
            "timestamp",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLogModel id={self.id} action={self.action} "
            f"actor={self.actor_email} resource={self.resource_type}:{self.resource_id}>"
        )
