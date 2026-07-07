"""Compliance assessment use cases.

Manages the complete assessment workflow from request through
execution, review, approval, and remediation tracking.
"""

from datetime import date
from typing import Any, Optional
from uuid import UUID

from regulaforge.application.use_cases.base import UseCase
from regulaforge.config.constants import AssessmentStatus, RiskLevel
from regulaforge.domain.entities.compliance_assessment import (
    ComplianceAssessment,
    ComplianceFinding,
)
from regulaforge.domain.repositories.assessment_repository import AssessmentRepository
from regulaforge.domain.repositories.base import EntityNotFoundError
from regulaforge.domain.repositories.entity_repository import EntityRepository
from regulaforge.domain.repositories.regulation_repository import RegulationRepository


class CreateAssessmentUseCase(UseCase):
    """Use case for creating a new compliance assessment."""

    def __init__(
        self,
        assessment_repo: AssessmentRepository,
        entity_repo: EntityRepository,
        regulation_repo: RegulationRepository,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._assessment_repo = assessment_repo
        self._entity_repo = entity_repo
        self._regulation_repo = regulation_repo

    async def execute(
        self,
        title: str,
        entity_id: UUID,
        regulation_ids: list[UUID],
        assessor_id: UUID,
        due_date: date,
        scope_description: Optional[str] = None,
        created_by: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ComplianceAssessment:
        """Create a new compliance assessment.

        Args:
            title: Assessment title.
            entity_id: Entity being assessed.
            regulation_ids: Regulations to assess against.
            assessor_id: User conducting the assessment.
            due_date: Assessment due date.
            scope_description: Optional scope description.
            created_by: User creating the assessment.
            metadata: Optional metadata.

        Returns:
            The created ComplianceAssessment.
        """
        self.logger.info(
            "Creating assessment: entity=%s regulations=%d",
            entity_id, len(regulation_ids),
        )

        # Validate entity exists
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError("AssessableEntity", entity_id)

        # Validate all regulations exist
        for reg_id in regulation_ids:
            reg = await self._regulation_repo.get_by_id(reg_id)
            if not reg:
                raise EntityNotFoundError("Regulation", reg_id)

        assessment = ComplianceAssessment(
            title=title,
            entity_id=entity_id,
            entity_type=entity.entity_type.value,
            regulation_ids=regulation_ids,
            assessor_id=assessor_id,
            due_date=due_date,
            status=AssessmentStatus.SCHEDULED,
            scope_description=scope_description,
            metadata=metadata,
            created_by=created_by,
        )

        saved = await self._assessment_repo.save(assessment)
        await self._publish_events(saved)
        self.logger.info("Assessment created: id=%s", saved.id)
        return saved


class StartAssessmentUseCase(UseCase):
    """Use case for starting a scheduled assessment."""

    def __init__(self, assessment_repo: AssessmentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._assessment_repo = assessment_repo

    async def execute(self, assessment_id: UUID, started_by: UUID) -> ComplianceAssessment:
        assessment = await self._assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise EntityNotFoundError("ComplianceAssessment", assessment_id)

        assessment.start(started_by)
        saved = await self._assessment_repo.save(assessment)
        await self._publish_events(saved)
        self.logger.info("Assessment started: id=%s", assessment_id)
        return saved


class AddFindingUseCase(UseCase):
    """Use case for adding a finding to an assessment."""

    def __init__(self, assessment_repo: AssessmentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._assessment_repo = assessment_repo

    async def execute(
        self,
        assessment_id: UUID,
        requirement_code: str,
        title: str,
        description: str,
        risk_level: RiskLevel,
        impact_score: Optional[float] = None,
        likelihood_score: Optional[float] = None,
        remediation_recommendation: Optional[str] = None,
        assigned_to: Optional[UUID] = None,
        added_by: Optional[UUID] = None,
    ) -> ComplianceAssessment:
        assessment = await self._assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise EntityNotFoundError("ComplianceAssessment", assessment_id)

        finding = ComplianceFinding(
            requirement_code=requirement_code,
            title=title,
            description=description,
            risk_level=risk_level,
            impact_score=impact_score,
            likelihood_score=likelihood_score,
            remediation_recommendation=remediation_recommendation,
            assigned_to=assigned_to,
        )

        assessment.add_finding(finding)
        assessment.mark_updated(added_by)
        saved = await self._assessment_repo.save(assessment)
        await self._publish_events(saved)
        self.logger.info(
            "Finding added: assessment=%s finding=%s risk=%s",
            assessment_id, title, risk_level.value,
        )
        return saved


class CompleteAssessmentUseCase(UseCase):
    """Use case for completing an assessment."""

    def __init__(self, assessment_repo: AssessmentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._assessment_repo = assessment_repo

    async def execute(
        self, assessment_id: UUID, score: float, completed_by: UUID
    ) -> ComplianceAssessment:
        assessment = await self._assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise EntityNotFoundError("ComplianceAssessment", assessment_id)

        assessment.complete(score, completed_by)
        saved = await self._assessment_repo.save(assessment)
        await self._publish_events(saved)
        self.logger.info(
            "Assessment completed: id=%s score=%.1f level=%s",
            assessment_id, score, assessment.get_compliance_level().value,
        )
        return saved


class ApproveAssessmentUseCase(UseCase):
    """Use case for approving a completed assessment."""

    def __init__(self, assessment_repo: AssessmentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._assessment_repo = assessment_repo

    async def execute(self, assessment_id: UUID, reviewer_id: UUID) -> ComplianceAssessment:
        assessment = await self._assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise EntityNotFoundError("ComplianceAssessment", assessment_id)

        assessment.approve(reviewer_id)
        saved = await self._assessment_repo.save(assessment)
        await self._publish_events(saved)
        self.logger.info("Assessment approved: id=%s", assessment_id)
        return saved


class GetAssessmentUseCase(UseCase):
    """Use case for retrieving an assessment."""

    def __init__(self, assessment_repo: AssessmentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._assessment_repo = assessment_repo

    async def execute(self, assessment_id: UUID) -> ComplianceAssessment:
        assessment = await self._assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise EntityNotFoundError("ComplianceAssessment", assessment_id)
        return assessment


class ListAssessmentsUseCase(UseCase):
    """Use case for listing assessments with filters."""

    def __init__(self, assessment_repo: AssessmentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._assessment_repo = assessment_repo

    async def execute(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ComplianceAssessment], int]:
        return await self._assessment_repo.search(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
