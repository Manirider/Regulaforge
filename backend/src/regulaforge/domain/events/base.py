"""Base domain event for event-driven architecture.

All domain events inherit from ``DomainEvent``. Events are registered on
entities via ``entity.register_event(event)`` and dispatched by the
event publisher or unit of work after persistence.

Usage::

    @dataclass
    class RegulationPublished(DomainEvent):
        regulation_id: UUID = field(default_factory=uuid4)
        title: str = ""
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass
class DomainEvent:
    """Base class for all domain events.

    Attributes:
        event_id: Unique event identifier (auto-generated).
        event_type: Dot-separated event type string (e.g. ``"regulation.published"``).
        timestamp: UTC timestamp of when the event occurred.
        aggregate_id: ID of the aggregate that raised the event.
        aggregate_type: Type name of the aggregate (e.g. ``"Regulation"``).
        data: Arbitrary event payload.
        correlation_id: Traces a chain of related operations.
        causation_id: ID of the event/command that caused this event.
        tenant_id: Multi-tenant isolation scope.
        version: Event schema version for backward-compatible evolution.
        metadata: Extensible metadata bag for cross-cutting concerns.
    """

    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    aggregate_id: UUID | None = None
    aggregate_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    causation_id: str | None = None
    tenant_id: str | None = None
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary for messaging/logging."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "aggregate_type": self.aggregate_type,
            "data": self.data,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "tenant_id": self.tenant_id,
            "version": self.version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DomainEvent":
        """Reconstruct event from dictionary."""
        event_id_raw = payload.get("event_id")
        agg_id_raw = payload.get("aggregate_id")
        return cls(
            event_id=UUID(event_id_raw) if event_id_raw else uuid4(),
            event_type=payload.get("event_type", ""),
            timestamp=datetime.fromisoformat(payload["timestamp"])
            if "timestamp" in payload
            else datetime.now(timezone.utc),
            aggregate_id=UUID(agg_id_raw) if agg_id_raw else None,
            aggregate_type=payload.get("aggregate_type", ""),
            data=payload.get("data", {}),
            correlation_id=payload.get("correlation_id"),
            causation_id=payload.get("causation_id"),
            tenant_id=payload.get("tenant_id"),
            version=payload.get("version", 1),
            metadata=payload.get("metadata", {}),
        )
