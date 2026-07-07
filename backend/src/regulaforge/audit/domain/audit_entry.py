"""Audit entry domain entity for event-sourced audit logging.

Represents a single auditable action that occurred in the system.
This is NOT a DomainEntity subclass; it is an event-sourced value
object with its own identity and timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.config.constants import AuditAction


@dataclass
class AuditEntry:
    """Immutable audit entry representing a single auditable action.

    Captures who did what, to which resource, when, and from where.
    Used for compliance auditing, forensics, and security analysis.
    """

    id: UUID
    action: AuditAction
    actor_id: UUID
    actor_email: str
    tenant_id: UUID
    resource_type: str
    resource_id: str
    details: Optional[dict[str, Any]] = None
    changes: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        action: AuditAction,
        actor_id: UUID,
        actor_email: str,
        tenant_id: UUID,
        resource_type: str,
        resource_id: str,
        details: Optional[dict[str, Any]] = None,
        changes: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
        id: Optional[UUID] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditEntry:
        """Factory method to create a new AuditEntry with auto-populated fields.

        Args:
            action: The auditable action performed.
            actor_id: UUID of the user who performed the action.
            actor_email: Email of the acting user.
            tenant_id: Tenant context UUID.
            resource_type: Type of resource affected (e.g. "regulation").
            resource_id: Identifier of the specific resource.
            details: Free-form details about the action.
            changes: Dictionary with old/new values for change tracking.
            ip_address: Source IP address of the request.
            user_agent: User agent string from the request.
            correlation_id: Distributed tracing correlation ID.
            id: Optional explicit UUID (auto-generated if omitted).
            timestamp: Optional explicit timestamp (defaults to now).

        Returns:
            A fully populated AuditEntry instance.
        """
        return cls(
            id=id or uuid4(),
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            timestamp=timestamp or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this audit entry to a dictionary.

        Returns:
            Dictionary representation suitable for persistence or API output.
        """
        return {
            "id": str(self.id),
            "action": self.action.value,
            "actor_id": str(self.actor_id),
            "actor_email": self.actor_email,
            "tenant_id": str(self.tenant_id),
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details or {},
            "changes": self.changes or {},
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<AuditEntry id={self.id} action={self.action.value} "
            f"actor={self.actor_email} resource={self.resource_type}:{self.resource_id}>"
        )
