"""Tenant repository interface (port).

Defines the contract for tenant persistence and multi-tenant
isolation lookups.
"""

from abc import abstractmethod
from typing import Optional

from regulaforge.domain.entities.tenant import Tenant
from regulaforge.domain.repositories.base import SearchableRepository


class TenantRepository(SearchableRepository[Tenant]):
    """Repository interface for Tenant aggregate persistence.

    Extends SearchableRepository with tenant-specific queries
    including slug-based lookups for URL routing.
    """

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Retrieve a tenant by its URL-friendly slug.

        Args:
            slug: The tenant slug (e.g., 'acme-corp').

        Returns:
            The Tenant if found, None otherwise.
        """
        ...
