"""Repository port interfaces.

Defines the contracts for data access operations that infrastructure
implementations must fulfill. These are the outgoing ports in
hexagonal architecture, separated from domain entity definitions
to avoid coupling domain logic to persistence patterns.
"""

from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar
from uuid import UUID

from regulaforge.domain.entities.base import DomainEntity

T = TypeVar("T", bound=DomainEntity)


class BaseRepository(ABC, Generic[T]):
    """Abstract generic repository port.

    All domain repository interfaces extend this contract.
    """

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Persist a new or updated entity.

        Args:
            entity: The domain entity to save.

        Returns:
            The saved entity with any generated fields populated.

        Raises:
            RepositoryError: If persistence fails.
        """
        ...

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> Optional[T]:
        """Retrieve an entity by its unique identifier.

        Args:
            entity_id: The entity UUID.

        Returns:
            The entity if found, None otherwise.
        """
        ...

    @abstractmethod
    async def delete(self, entity_id: UUID) -> None:
        """Delete an entity by its identifier.

        Args:
            entity_id: The entity UUID to delete.

        Raises:
            RepositoryError: If deletion fails or entity not found.
        """
        ...

    @abstractmethod
    async def exists(self, entity_id: UUID) -> bool:
        """Check if an entity exists by its identifier.

        Args:
            entity_id: The entity UUID to check.

        Returns:
            True if the entity exists, False otherwise.
        """
        ...


class SearchableRepository(BaseRepository[T], ABC):
    """Repository port with search and pagination capabilities."""

    @abstractmethod
    async def search(
        self,
        filters: Optional[dict[str, object]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[T], int]:
        """Search entities with filtering, sorting, and pagination.

        Args:
            filters: Dictionary of field filters.
            sort_by: Field name to sort by.
            sort_order: 'asc' or 'desc'.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (entities list, total count).
        """
        ...

    @abstractmethod
    async def count(self, filters: Optional[dict[str, object]] = None) -> int:
        """Count entities matching the given filters.

        Args:
            filters: Dictionary of field filters.

        Returns:
            Total count of matching entities.
        """
        ...


from regulaforge.common.exceptions import (
    RepositoryError,
    EntityNotFoundError,
    DuplicateEntityError,
)  # noqa: F401 - re-exported from common for backward compatibility
