"""Entity domain events."""

from typing import Any
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class EntityCreated(DomainEvent):
    """Emitted when a new assessable entity is created."""

    def __init__(self, entity_id: UUID, name: str, entity_type: str, tenant_id: UUID, **kwargs: Any) -> None:
        super().__init__(
            event_type="entity.created",
            aggregate_id=entity_id,
            aggregate_type="assessable_entity",
            data={
                "name": name,
                "entity_type": entity_type,
                "tenant_id": str(tenant_id),
            },
            **kwargs,
        )


class EntityUpdated(DomainEvent):
    """Emitted when an assessable entity is modified."""

    def __init__(self, entity_id: UUID, name: str, changes: dict, **kwargs: Any) -> None:
        super().__init__(
            event_type="entity.updated",
            aggregate_id=entity_id,
            aggregate_type="assessable_entity",
            data={"name": name, "changes": changes},
            **kwargs,
        )


class EntityDeactivated(DomainEvent):
    """Emitted when an assessable entity is deactivated."""

    def __init__(self, entity_id: UUID, name: str, **kwargs: Any) -> None:
        super().__init__(
            event_type="entity.deactivated",
            aggregate_id=entity_id,
            aggregate_type="assessable_entity",
            data={"name": name},
            **kwargs,
        )


class EntityActivated(DomainEvent):
    """Emitted when an assessable entity is reactivated."""

    def __init__(self, entity_id: UUID, name: str, **kwargs: Any) -> None:
        super().__init__(
            event_type="entity.activated",
            aggregate_id=entity_id,
            aggregate_type="assessable_entity",
            data={"name": name},
            **kwargs,
        )
