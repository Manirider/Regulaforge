"""AssessableEntity repository interface."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from regulaforge.domain.entities.entity import AssessableEntity
from regulaforge.domain.repositories.base import SearchableRepository


class EntityRepository(SearchableRepository[AssessableEntity], ABC):
    """Repository interface for AssessableEntity aggregate."""

    @abstractmethod
    async def get_by_tenant(
        self, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[AssessableEntity], int]:
        """Get entities belonging to a tenant.

        Args:
            tenant_id: The tenant UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (entities list, total count).
        """
        ...

    @abstractmethod
    async def get_by_type(
        self, entity_type: str, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[AssessableEntity], int]:
        """Get entities by type within a tenant.

        Args:
            entity_type: The entity type string.
            tenant_id: The tenant UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (entities list, total count).
        """
        ...

    @abstractmethod
    async def get_by_name(
        self, name: str, tenant_id: UUID
    ) -> Optional[AssessableEntity]:
        """Find an entity by name within a tenant.

        Args:
            name: The entity name.
            tenant_id: The tenant UUID.

        Returns:
            The entity if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_hierarchy(
        self, entity_id: UUID
    ) -> list[AssessableEntity]:
        """Get the hierarchy (parent chain) of an entity.

        Args:
            entity_id: The entity UUID.

        Returns:
            List of entities from root to the given entity.
        """
        ...

    @abstractmethod
    async def get_children(
        self, parent_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[AssessableEntity], int]:
        """Get direct child entities.

        Args:
            parent_id: The parent entity UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (entities list, total count).
        """
        ...
