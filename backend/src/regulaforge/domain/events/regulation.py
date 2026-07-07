"""Regulation domain events."""

from typing import Any
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class RegulationCreated(DomainEvent):
    """Emitted when a new regulation is created."""

    def __init__(self, regulation_id: UUID, code: str, title: str, **kwargs: Any) -> None:
        super().__init__(
            event_type="regulation.created",
            aggregate_id=regulation_id,
            aggregate_type="regulation",
            data={"code": code, "title": title},
            **kwargs,
        )


class RegulationUpdated(DomainEvent):
    """Emitted when a regulation is modified."""

    def __init__(self, regulation_id: UUID, code: str, changes: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(
            event_type="regulation.updated",
            aggregate_id=regulation_id,
            aggregate_type="regulation",
            data={"code": code, "changes": changes},
            **kwargs,
        )


class RegulationPublished(DomainEvent):
    """Emitted when a regulation is published (moved to active)."""

    def __init__(self, regulation_id: UUID, code: str, title: str, **kwargs: Any) -> None:
        super().__init__(
            event_type="regulation.published",
            aggregate_id=regulation_id,
            aggregate_type="regulation",
            data={"code": code, "title": title},
            **kwargs,
        )


class RegulationArchived(DomainEvent):
    """Emitted when a regulation is archived."""

    def __init__(self, regulation_id: UUID, code: str, **kwargs: Any) -> None:
        super().__init__(
            event_type="regulation.archived",
            aggregate_id=regulation_id,
            aggregate_type="regulation",
            data={"code": code},
            **kwargs,
        )


class RegulationSuperseded(DomainEvent):
    """Emitted when a regulation is superseded by a newer version."""

    def __init__(
        self, regulation_id: UUID, code: str, new_regulation_id: UUID, **kwargs: Any
    ) -> None:
        super().__init__(
            event_type="regulation.superseded",
            aggregate_id=regulation_id,
            aggregate_type="regulation",
            data={"code": code, "new_regulation_id": str(new_regulation_id)},
            **kwargs,
        )
