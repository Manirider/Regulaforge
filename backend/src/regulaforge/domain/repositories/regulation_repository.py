"""Regulation repository interface."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from regulaforge.domain.entities.regulation import Regulation
from regulaforge.domain.repositories.base import SearchableRepository


class RegulationRepository(SearchableRepository[Regulation], ABC):
    """Repository interface for Regulation aggregate.

    Defines the contract for regulation persistence beyond
    the standard CRUD operations.
    """

    @abstractmethod
    async def get_by_code(self, code: str) -> Optional[Regulation]:
        """Find a regulation by its unique code.

        Args:
            code: The regulation code (e.g., 'GDPR', 'SOX-404').

        Returns:
            The Regulation if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_active_by_category(
        self, category: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Regulation], int]:
        """Get active regulations by category.

        Args:
            category: The regulation category.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (regulations list, total count).
        """
        ...

    @abstractmethod
    async def get_by_jurisdiction(
        self, jurisdiction: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Regulation], int]:
        """Get regulations by jurisdiction.

        Args:
            jurisdiction: The jurisdiction string.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (regulations list, total count).
        """
        ...

    @abstractmethod
    async def get_all_active(self, page: int = 1, page_size: int = 20) -> tuple[list[Regulation], int]:
        """Get all currently active regulations.

        Args:
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (regulations list, total count).
        """
        ...

    @abstractmethod
    async def search_by_text(
        self, query: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Regulation], int]:
        """Full-text search across regulation title, code, and description.

        Args:
            query: The search query string.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (regulations list, total count).
        """
        ...

    @abstractmethod
    async def get_version_history(self, regulation_id: UUID) -> list[dict]:
        """Get the version history of a regulation.

        Args:
            regulation_id: The regulation UUID.

        Returns:
            List of version metadata dictionaries.
        """
        ...

    @abstractmethod
    async def bulk_save(self, regulations: list[Regulation]) -> list[Regulation]:
        """Bulk persist multiple regulations.

        Args:
            regulations: List of regulations to save.

        Returns:
            List of saved regulations.
        """
        ...
