"""Base entity with common fields and behavior for all domain entities."""

from abc import ABC
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.domain.events.base import DomainEvent


class DomainEntity(ABC):  # noqa: B024
    """Abstract base for all domain entities.

    Provides identity comparison, timestamps, optimistic concurrency,
    multi-tenant isolation, soft-delete, and domain event registration.
    All domain entities MUST inherit from this class.
    """

    def __init__(
        self,
        id: Optional[UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        created_by: Optional[UUID] = None,
        updated_by: Optional[UUID] = None,
        version: int = 1,
        tenant_id: Optional[UUID] = None,
        is_deleted: bool = False,
        deleted_at: Optional[datetime] = None,
    ) -> None:
        self._id: UUID = id or uuid4()
        self._created_at: datetime = created_at or datetime.now(timezone.utc)
        self._updated_at: datetime = updated_at or datetime.now(timezone.utc)
        self._created_by: Optional[UUID] = created_by
        self._updated_by: Optional[UUID] = updated_by
        self._version: int = version
        self._tenant_id: Optional[UUID] = tenant_id
        self._is_deleted: bool = is_deleted
        self._deleted_at: Optional[datetime] = deleted_at
        self._events: list["DomainEvent"] = []

    @property
    def id(self) -> UUID:
        """Read-only entity identity."""
        return self._id

    @property
    def created_at(self) -> datetime:
        """Entity creation timestamp (UTC)."""
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        """Last modification timestamp (UTC)."""
        return self._updated_at

    @property
    def created_by(self) -> Optional[UUID]:
        """User who created this entity."""
        return self._created_by

    @property
    def updated_by(self) -> Optional[UUID]:
        """User who last modified this entity."""
        return self._updated_by

    @property
    def version(self) -> int:
        """Optimistic concurrency version."""
        return self._version

    @property
    def tenant_id(self) -> Optional[UUID]:
        """Tenant identifier for multi-tenant isolation."""
        return self._tenant_id

    @property
    def is_deleted(self) -> bool:
        """Indicates if the entity has been soft-deleted."""
        return self._is_deleted

    @property
    def deleted_at(self) -> Optional[datetime]:
        """Timestamp of when the entity was soft-deleted."""
        return self._deleted_at

    def mark_updated(self, by: Optional[UUID] = None) -> None:
        """Update the modification timestamp and increment version."""
        self._updated_at = datetime.now(timezone.utc)
        self._updated_by = by or self._updated_by
        self._version += 1

    def mark_deleted(self, by: Optional[UUID] = None) -> None:
        """Mark the entity as soft-deleted."""
        self._is_deleted = True
        self._deleted_at = datetime.now(timezone.utc)
        self._updated_by = by or self._updated_by
        self._version += 1

    def restore(self, by: Optional[UUID] = None) -> None:
        """Restore a soft-deleted entity.

        Args:
            by: The user performing the restoration.
        """
        self._is_deleted = False
        self._deleted_at = None
        self.mark_updated(by)

    def register_event(self, event: "DomainEvent") -> None:
        """Register a domain event (eventual consistency)."""
        self._events.append(event)

    def clear_events(self) -> list["DomainEvent"]:
        """Retrieve and clear all pending domain events."""
        events = list(self._events)
        self._events.clear()
        return events

    def to_dict(self) -> dict[str, Any]:
        """Serialize entity to dictionary for persistence."""
        return {
            "id": str(self._id),
            "created_at": self._created_at.isoformat(),
            "updated_at": self._updated_at.isoformat(),
            "created_by": str(self._created_by) if self._created_by else None,
            "updated_by": str(self._updated_by) if self._updated_by else None,
            "version": self._version,
            "tenant_id": str(self._tenant_id) if self._tenant_id else None,
            "is_deleted": self._is_deleted,
            "deleted_at": self._deleted_at.isoformat() if self._deleted_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainEntity":
        """Reconstitute entity from dictionary (factory method)."""
        return cls(**data)

    def __eq__(self, other: object) -> bool:
        """Entity equality is based on identity."""
        if not isinstance(other, DomainEntity):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        """Hash based on identity."""
        return hash(self._id)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self._id}>"

