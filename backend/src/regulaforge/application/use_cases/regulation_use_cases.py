"""Regulation management use cases.

Handles the complete lifecycle of regulations from creation
through publication, amendment, and archival.
"""

from datetime import date
from typing import Any, Optional
from uuid import UUID

from regulaforge.application.use_cases.base import UseCase
from regulaforge.config.constants import RegulationCategory, RegulationJurisdiction, RegulationStatus
from regulaforge.domain.entities.regulation import Regulation, RegulationRequirement
from regulaforge.domain.events.regulation import RegulationCreated, RegulationUpdated
from regulaforge.domain.repositories.base import DuplicateEntityError, EntityNotFoundError
from regulaforge.domain.repositories.regulation_repository import RegulationRepository


class CreateRegulationUseCase(UseCase):
    """Use case for creating a new regulation."""

    def __init__(self, regulation_repo: RegulationRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._regulation_repo = regulation_repo

    async def execute(
        self,
        title: str,
        code: str,
        description: str,
        category: RegulationCategory,
        jurisdiction: RegulationJurisdiction,
        issuing_body: str,
        effective_date: date,
        created_by: UUID,
        tags: Optional[list[str]] = None,
        parent_regulation_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Regulation:
        """Create a new regulation.

        Args:
            title: Regulation title.
            code: Unique regulation code.
            description: Detailed description.
            category: Regulation category.
            jurisdiction: Applicable jurisdiction.
            issuing_body: Regulatory body.
            effective_date: Date of effect.
            created_by: User creating the regulation.
            tags: Optional tags.
            parent_regulation_id: Optional parent regulation.
            metadata: Optional metadata.

        Returns:
            The created Regulation.

        Raises:
            DuplicateEntityError: If a regulation with the same code exists.
            ValueError: If validation fails.
        """
        self.logger.info("Creating regulation: code=%s, title=%s", code, title)

        # Check uniqueness
        existing = await self._regulation_repo.get_by_code(code)
        if existing:
            raise DuplicateEntityError("Regulation", "code", code)

        regulation = Regulation(
            title=title,
            code=code,
            description=description,
            category=category,
            jurisdiction=jurisdiction,
            issuing_body=issuing_body,
            effective_date=effective_date,
            status=RegulationStatus.DRAFT,
            tags=tags,
            parent_regulation_id=parent_regulation_id,
            metadata=metadata,
            created_by=created_by,
        )

        saved = await self._regulation_repo.save(regulation)
        await self._publish_event(RegulationCreated(
            regulation_id=saved.id,
            code=saved.code,
            title=saved.title,
        ))
        self.logger.info("Regulation created: id=%s code=%s", saved.id, code)
        return saved


class UpdateRegulationUseCase(UseCase):
    """Use case for updating an existing regulation."""

    def __init__(self, regulation_repo: RegulationRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._regulation_repo = regulation_repo

    async def execute(
        self,
        regulation_id: UUID,
        updated_by: UUID,
        **updates: Any,
    ) -> Regulation:
        """Update an existing regulation.

        Args:
            regulation_id: The regulation UUID.
            updated_by: User making the update.
            **updates: Fields to update.

        Returns:
            The updated Regulation.
        """
        self.logger.info("Updating regulation: id=%s", regulation_id)

        regulation = await self._regulation_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("Regulation", regulation_id)

        changes = {}
        for field, value in updates.items():
            if hasattr(regulation, f"_{field}") and value is not None:
                setattr(regulation, f"_{field}", value)
                changes[field] = value

        regulation.mark_updated(updated_by)
        saved = await self._regulation_repo.save(regulation)

        if changes:
            await self._publish_event(RegulationUpdated(
                regulation_id=saved.id,
                code=saved.code,
                changes=changes,
            ))

        self.logger.info("Regulation updated: id=%s changes=%s", regulation_id, list(changes.keys()))
        return saved


class PublishRegulationUseCase(UseCase):
    """Use case for publishing a draft regulation."""

    def __init__(self, regulation_repo: RegulationRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._regulation_repo = regulation_repo

    async def execute(self, regulation_id: UUID, published_by: UUID) -> Regulation:
        regulation = await self._regulation_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("Regulation", regulation_id)

        regulation.publish(published_by)
        saved = await self._regulation_repo.save(regulation)
        await self._publish_events(saved)
        self.logger.info("Regulation published: id=%s code=%s", regulation_id, saved.code)
        return saved


class GetRegulationUseCase(UseCase):
    """Use case for retrieving a regulation."""

    def __init__(self, regulation_repo: RegulationRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._regulation_repo = regulation_repo

    async def execute(self, regulation_id: UUID) -> Regulation:
        regulation = await self._regulation_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("Regulation", regulation_id)
        return regulation


class SearchRegulationsUseCase(UseCase):
    """Use case for searching regulations."""

    def __init__(self, regulation_repo: RegulationRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._regulation_repo = regulation_repo

    async def execute(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Regulation], int]:
        return await self._regulation_repo.search(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )


class AddRequirementUseCase(UseCase):
    """Use case for adding a requirement to a regulation."""

    def __init__(self, regulation_repo: RegulationRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._regulation_repo = regulation_repo

    async def execute(
        self,
        regulation_id: UUID,
        code: str,
        title: str,
        description: str,
        is_mandatory: bool = True,
        risk_weight: float = 1.0,
        guidance: Optional[str] = None,
        references: Optional[list[str]] = None,
        parent_requirement_code: Optional[str] = None,
        added_by: Optional[UUID] = None,
    ) -> Regulation:
        regulation = await self._regulation_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("Regulation", regulation_id)

        requirement = RegulationRequirement(
            code=code,
            title=title,
            description=description,
            parent_requirement_code=parent_requirement_code,
            is_mandatory=is_mandatory,
            risk_weight=risk_weight,
            guidance=guidance,
            references=references,
        )
        regulation.add_requirement(requirement)
        regulation.mark_updated(added_by)

        saved = await self._regulation_repo.save(regulation)
        self.logger.info("Requirement added: regulation=%s requirement=%s", regulation_id, code)
        return saved
