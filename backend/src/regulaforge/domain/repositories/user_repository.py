"""User repository interface (port).

Defines the contract for user persistence and authentication
operations. All implementations must satisfy this interface.
"""

from abc import abstractmethod
from typing import Optional
from uuid import UUID

from regulaforge.domain.entities.user import User
from regulaforge.domain.repositories.base import SearchableRepository


class UserRepository(SearchableRepository[User]):
    """Repository interface for User aggregate persistence.

    Extends SearchableRepository with user-specific queries
    including email lookup, tenant scoping, and authentication.
    """

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by their email address.

        Args:
            email: The user's email address.

        Returns:
            The User if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_by_tenant(self, tenant_id: UUID) -> list[User]:
        """Retrieve all users belonging to a tenant.

        Args:
            tenant_id: The tenant UUID.

        Returns:
            List of User entities for the given tenant.
        """
        ...

    @abstractmethod
    async def get_by_role(self, role_id: UUID) -> list[User]:
        """Retrieve all users assigned a specific role.

        Args:
            role_id: The role UUID.

        Returns:
            List of User entities with the given role.
        """
        ...

    @abstractmethod
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password.

        Args:
            email: The user's email address.
            password: The plain-text password to verify.

        Returns:
            The authenticated User if credentials match, None otherwise.
        """
        ...
