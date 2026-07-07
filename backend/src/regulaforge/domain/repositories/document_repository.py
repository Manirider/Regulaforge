"""Document repository interface."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from regulaforge.domain.entities.document import Document
from regulaforge.domain.repositories.base import SearchableRepository


class DocumentRepository(SearchableRepository[Document], ABC):
    """Repository interface for Document aggregate."""

    @abstractmethod
    async def get_by_tenant(
        self, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[Document], int]:
        """Get documents belonging to a tenant.

        Args:
            tenant_id: The tenant UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (documents list, total count).
        """
        ...

    @abstractmethod
    async def get_by_artifact_type(
        self, artifact_type: str, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[Document], int]:
        """Get documents by artifact type within a tenant.

        Args:
            artifact_type: The artifact type string.
            tenant_id: The tenant UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (documents list, total count).
        """
        ...

    @abstractmethod
    async def get_by_checksum(self, checksum: str) -> Optional[Document]:
        """Find a document by its checksum.

        Args:
            checksum: The SHA-256 checksum.

        Returns:
            The document if found, None otherwise.
        """
        ...
