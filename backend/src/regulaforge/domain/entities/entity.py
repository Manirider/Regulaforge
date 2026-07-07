"""Assessable Entity aggregate.

Represents any entity that can be assessed for compliance:
organizations, departments, products, services, systems, processes, etc.
"""

from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.entities.base import DomainEntity
from regulaforge.domain.enums import EntityType


class AssessableEntity(DomainEntity):
    """An entity subject to compliance assessment.

    Acts as an aggregate root that owns associated metadata,
    documentation, and compliance history.
    """

    def __init__(
        self,
        name: str,
        entity_type: EntityType,
        tenant_id: UUID,
        description: Optional[str] = None,
        parent_entity_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        attributes: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._validate(name, entity_type, tenant_id)

        self._name: str = name
        self._entity_type: EntityType = entity_type
        self._tenant_id: UUID = tenant_id
        self._description: Optional[str] = description
        self._parent_entity_id: Optional[UUID] = parent_entity_id
        self._tags: list[str] = tags or []
        self._attributes: dict[str, Any] = attributes or {}
        self._active: bool = True

    @staticmethod
    def _validate(name: str, entity_type: EntityType, tenant_id: UUID) -> None:
        if not name or len(name.strip()) < 2:
            raise ValueError("Entity name must be at least 2 characters")
        if len(name) > 200:
            raise ValueError("Entity name must not exceed 200 characters")
        if not isinstance(entity_type, EntityType):
            raise TypeError("Invalid entity type")
        if not tenant_id:
            raise ValueError("Tenant ID is required")

    @property
    def name(self) -> str:
        return self._name

    @property
    def entity_type(self) -> EntityType:
        return self._entity_type

    @property
    def tenant_id(self) -> UUID:
        return self._tenant_id

    @property
    def description(self) -> Optional[str]:
        return self._description

    @property
    def parent_entity_id(self) -> Optional[UUID]:
        return self._parent_entity_id

    @property
    def tags(self) -> list[str]:
        return list(self._tags)

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(self._attributes)

    @property
    def is_active(self) -> bool:
        return self._active

    def deactivate(self, by: Optional[UUID] = None) -> None:
        """Deactivate this entity."""
        self._active = False
        self.mark_updated(by)

    def activate(self, by: Optional[UUID] = None) -> None:
        """Reactivate this entity."""
        self._active = True
        self.mark_updated(by)

    def update_attributes(self, attributes: dict[str, Any], by: Optional[UUID] = None) -> None:
        """Update entity attributes."""
        self._attributes.update(attributes)
        self.mark_updated(by)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "name": self._name,
            "entity_type": self._entity_type.value,
            "tenant_id": str(self._tenant_id),
            "description": self._description,
            "parent_entity_id": str(self._parent_entity_id) if self._parent_entity_id else None,
            "tags": self._tags,
            "attributes": self._attributes,
            "is_active": self._active,
        })
        return base

    def __repr__(self) -> str:
        return f"<AssessableEntity {self._name} [{self._entity_type.value}]>"
