"""Compliance Assessment repository interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from regulaforge.domain.entities.compliance_assessment import ComplianceAssessment
from regulaforge.domain.repositories.base import SearchableRepository


class AssessmentRepository(SearchableRepository[ComplianceAssessment], ABC):
    """Repository interface for ComplianceAssessment aggregate."""

    @abstractmethod
    async def get_by_entity(
        self, entity_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        """Get assessments for a specific entity.

        Args:
            entity_id: The entity UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (assessments list, total count).
        """
        ...

    @abstractmethod
    async def get_by_regulation(
        self, regulation_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        """Get assessments for a specific regulation.

        Args:
            regulation_id: The regulation UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (assessments list, total count).
        """
        ...

    @abstractmethod
    async def get_by_assignee(
        self, assignee_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        """Get assessments assigned to a specific user.

        Args:
            assignee_id: The user UUID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (assessments list, total count).
        """
        ...

    @abstractmethod
    async def get_by_status(
        self, status: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        """Get assessments by their current status.

        Args:
            status: The assessment status string.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (assessments list, total count).
        """
        ...

    @abstractmethod
    async def get_overdue(self, page: int = 1, page_size: int = 20) -> tuple[list[ComplianceAssessment], int]:
        """Get assessments past their due date.

        Args:
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (assessments list, total count).
        """
        ...

    @abstractmethod
    async def get_compliance_summary(
        self, entity_id: UUID
    ) -> dict:
        """Get compliance summary statistics for an entity.

        Args:
            entity_id: The entity UUID.

        Returns:
            Dictionary with compliance summary metrics.
        """
        ...
