"""Role repository interface (port).

Defines the contract for role persistence and permission-based
lookup operations.
"""

from abc import abstractmethod
from typing import Optional

from regulaforge.domain.entities.role import Role
from regulaforge.domain.repositories.base import SearchableRepository


class RoleRepository(SearchableRepository[Role]):
    """Repository interface for Role aggregate persistence.

    Extends SearchableRepository with role-specific queries
    including name lookup and permission-based searches.
    """

    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Role]:
        """Retrieve a role by its unique name.

        Args:
            name: The role name (case-insensitive).

        Returns:
            The Role if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_by_permission(self, permission_key: str) -> list[Role]:
        """Retrieve all roles that include a specific permission.

        Args:
            permission_key: The permission key (e.g., 'regulation:create').

        Returns:
            List of Role entities that grant the specified permission.
        """
        ...
