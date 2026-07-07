"""Entity management use cases.

Handles the lifecycle of assessable entities from creation
through updates, hierarchy management, and deactivation.
"""

from typing import Any, Optional
from uuid import UUID

from regulaforge.application.use_cases.base import UseCase
from regulaforge.config.constants import EntityType
from regulaforge.domain.entities.entity import AssessableEntity
from regulaforge.domain.events.entity import (
    EntityActivated,
    EntityCreated,
    EntityDeactivated,
    EntityUpdated,
)
from regulaforge.domain.repositories.base import DuplicateEntityError, EntityNotFoundError
from regulaforge.domain.repositories.entity_repository import EntityRepository


class CreateEntityUseCase(UseCase):
    """Use case for creating a new assessable entity."""

    def __init__(self, entity_repo: EntityRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_repo = entity_repo

    async def execute(
        self,
        name: str,
        entity_type: EntityType,
        tenant_id: UUID,
        description: Optional[str] = None,
        parent_entity_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        attributes: Optional[dict[str, Any]] = None,
        created_by: Optional[UUID] = None,
    ) -> AssessableEntity:
        """Create a new assessable entity.

        Args:
            name: Entity name.
            entity_type: Type of entity.
            tenant_id: Tenant this entity belongs to.
            description: Optional description.
            parent_entity_id: Optional parent entity.
            tags: Optional searchable tags.
            attributes: Optional flexible attributes.
            created_by: User creating the entity.

        Returns:
            The created AssessableEntity.

        Raises:
            DuplicateEntityError: If an entity with the same name exists in the tenant.
            ValueError: If validation fails.
        """
        self.logger.info(
            "Creating entity: name=%s type=%s tenant=%s",
            name, entity_type.value, tenant_id,
        )

        # Check for duplicate name within tenant
        existing = await self._entity_repo.get_by_name(name, tenant_id)
        if existing:
            raise DuplicateEntityError("AssessableEntity", "name", name)

        entity = AssessableEntity(
            name=name,
            entity_type=entity_type,
            tenant_id=tenant_id,
            description=description,
            parent_entity_id=parent_entity_id,
            tags=tags,
            attributes=attributes,
            created_by=created_by,
        )

        saved = await self._entity_repo.save(entity)
        await self._publish_event(EntityCreated(
            entity_id=saved.id,
            name=saved.name,
            entity_type=saved.entity_type.value,
            tenant_id=saved.tenant_id,
        ))
        self.logger.info("Entity created: id=%s name=%s", saved.id, name)
        return saved


class GetEntityUseCase(UseCase):
    """Use case for retrieving an entity."""

    def __init__(self, entity_repo: EntityRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_repo = entity_repo

    async def execute(self, entity_id: UUID) -> AssessableEntity:
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError("AssessableEntity", entity_id)
        return entity


class UpdateEntityUseCase(UseCase):
    """Use case for updating an existing entity."""

    def __init__(self, entity_repo: EntityRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_repo = entity_repo

    async def execute(
        self,
        entity_id: UUID,
        updated_by: Optional[UUID] = None,
        **updates: Any,
    ) -> AssessableEntity:
        """Update an existing entity.

        Args:
            entity_id: The entity UUID.
            updated_by: User making the update.
            **updates: Fields to update (name, description, tags, attributes, parent_entity_id).

        Returns:
            The updated AssessableEntity.

        Raises:
            EntityNotFoundError: If entity not found.
            ValueError: If validation fails.
        """
        self.logger.info("Updating entity: id=%s", entity_id)

        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError("AssessableEntity", entity_id)

        changes = {}
        for field, value in updates.items():
            if value is not None:
                if field == "name":
                    entity._name = value
                    changes[field] = value
                elif field == "description":
                    entity._description = value
                    changes[field] = value
                elif field == "tags":
                    entity._tags = value
                    changes[field] = value
                elif field == "attributes":
                    entity.update_attributes(value)
                    changes[field] = value
                elif field == "parent_entity_id":
                    entity._parent_entity_id = value
                    changes[field] = value

        entity.mark_updated(updated_by)
        saved = await self._entity_repo.save(entity)

        if changes:
            await self._publish_event(EntityUpdated(
                entity_id=saved.id,
                name=saved.name,
                changes=changes,
            ))

        self.logger.info("Entity updated: id=%s changes=%s", entity_id, list(changes.keys()))
        return saved


class SearchEntitiesUseCase(UseCase):
    """Use case for searching entities."""

    def __init__(self, entity_repo: EntityRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_repo = entity_repo

    async def execute(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AssessableEntity], int]:
        return await self._entity_repo.search(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )


class GetEntityHierarchyUseCase(UseCase):
    """Use case for getting entity parent chain."""

    def __init__(self, entity_repo: EntityRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_repo = entity_repo

    async def execute(self, entity_id: UUID) -> list[AssessableEntity]:
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError("AssessableEntity", entity_id)

        hierarchy = await self._entity_repo.get_hierarchy(entity_id)
        self.logger.info("Entity hierarchy retrieved: id=%s depth=%d", entity_id, len(hierarchy))
        return hierarchy


class GetEntityChildrenUseCase(UseCase):
    """Use case for getting child entities."""

    def __init__(self, entity_repo: EntityRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_repo = entity_repo

    async def execute(
        self,
        parent_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AssessableEntity], int]:
        entity = await self._entity_repo.get_by_id(parent_id)
        if not entity:
            raise EntityNotFoundError("AssessableEntity", parent_id)

        return await self._entity_repo.get_children(
            parent_id=parent_id,
            page=page,
            page_size=page_size,
        )


class DeactivateEntityUseCase(UseCase):
    """Use case for deactivating or reactivating an entity."""

    def __init__(self, entity_repo: EntityRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_repo = entity_repo

    async def execute(
        self, entity_id: UUID, deactivate: bool = True, by: Optional[UUID] = None
    ) -> AssessableEntity:
        """Deactivate or reactivate an entity.

        Args:
            entity_id: The entity UUID.
            deactivate: True to deactivate, False to reactivate.
            by: User performing the action.

        Returns:
            The updated AssessableEntity.

        Raises:
            EntityNotFoundError: If entity not found.
        """
        self.logger.info(
            "%s entity: id=%s",
            "Deactivating" if deactivate else "Reactivating",
            entity_id,
        )

        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError("AssessableEntity", entity_id)

        if deactivate:
            entity.deactivate(by)
        else:
            entity.activate(by)

        saved = await self._entity_repo.save(entity)

        if deactivate:
            await self._publish_event(EntityDeactivated(
                entity_id=saved.id,
                name=saved.name,
            ))
        else:
            await self._publish_event(EntityActivated(
                entity_id=saved.id,
                name=saved.name,
            ))

        self.logger.info(
            "Entity %s: id=%s",
            "deactivated" if deactivate else "reactivated",
            entity_id,
        )
        return saved
