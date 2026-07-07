"""Unit tests for assessment use cases with mocked repositories."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from regulaforge.application.use_cases.assessment_use_cases import (
    AddFindingUseCase,
    ApproveAssessmentUseCase,
    CompleteAssessmentUseCase,
    CreateAssessmentUseCase,
    GetAssessmentUseCase,
    ListAssessmentsUseCase,
    StartAssessmentUseCase,
)
from regulaforge.config.constants import AssessmentStatus, EntityType, RiskLevel
from regulaforge.domain.entities.compliance_assessment import (
    ComplianceAssessment,
    ComplianceFinding,
)
from regulaforge.domain.entities.entity import AssessableEntity
from regulaforge.domain.entities.regulation import Regulation
from regulaforge.domain.repositories.base import EntityNotFoundError

pytestmark = pytest.mark.unit


class TestCreateAssessmentUseCase:
    """Tests for CreateAssessmentUseCase."""

    async def test_create_assessment_success(
        self,
        mock_assessment_repo,
        mock_entity_repo,
        mock_regulation_repo,
        mock_event_publisher,
        entity,
        regulation,
    ):
        use_case = CreateAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            entity_repo=mock_entity_repo,
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        mock_entity_repo.get_by_id.return_value = entity
        mock_regulation_repo.get_by_id.return_value = regulation
        mock_assessment_repo.save.return_value = ComplianceAssessment(
            id=uuid4(),
            title="GDPR Assessment",
            entity_id=entity.id,
            entity_type=entity.entity_type.value,
            regulation_ids=[regulation.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
        )

        result = await use_case.execute(
            title="GDPR Assessment",
            entity_id=entity.id,
            regulation_ids=[regulation.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
        )

        assert result.title == "GDPR Assessment"
        assert result.status == AssessmentStatus.SCHEDULED
        mock_assessment_repo.save.assert_called_once()

    async def test_create_assessment_nonexistent_entity(
        self,
        mock_assessment_repo,
        mock_entity_repo,
        mock_regulation_repo,
        mock_event_publisher,
        regulation,
    ):
        use_case = CreateAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            entity_repo=mock_entity_repo,
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        mock_entity_repo.get_by_id.return_value = None
        mock_regulation_repo.get_by_id.return_value = regulation

        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(
                title="Test Assessment",
                entity_id=uuid4(),
                regulation_ids=[regulation.id],
                assessor_id=uuid4(),
                due_date=date(2024, 12, 31),
            )

        mock_assessment_repo.save.assert_not_called()

    async def test_create_assessment_nonexistent_regulation(
        self,
        mock_assessment_repo,
        mock_entity_repo,
        mock_regulation_repo,
        mock_event_publisher,
        entity,
    ):
        use_case = CreateAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            entity_repo=mock_entity_repo,
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        mock_entity_repo.get_by_id.return_value = entity
        mock_regulation_repo.get_by_id.return_value = None

        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(
                title="Test Assessment",
                entity_id=entity.id,
                regulation_ids=[uuid4()],
                assessor_id=uuid4(),
                due_date=date(2024, 12, 31),
            )

        mock_assessment_repo.save.assert_not_called()

    async def test_publishes_events_on_start(
        self,
        mock_assessment_repo,
        mock_event_publisher,
        assessment,
    ):
        use_case = StartAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.side_effect = lambda a: a

        await use_case.execute(assessment.id, uuid4())

        assert mock_event_publisher.publish_batch.called


class TestStartAssessmentUseCase:
    """Tests for StartAssessmentUseCase."""

    async def test_start_assessment_success(
        self,
        mock_assessment_repo,
        mock_event_publisher,
        assessment,
    ):
        use_case = StartAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.side_effect = lambda a: a

        result = await use_case.execute(assessment.id, uuid4())

        assert result.status == AssessmentStatus.IN_PROGRESS
        mock_assessment_repo.save.assert_called_once()

    async def test_start_nonexistent_assessment(
        self,
        mock_assessment_repo,
        mock_event_publisher,
    ):
        use_case = StartAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        mock_assessment_repo.get_by_id.return_value = None

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(uuid4(), uuid4())


class TestAddFindingUseCase:
    """Tests for AddFindingUseCase."""

    async def test_add_finding_success(
        self,
        mock_assessment_repo,
        mock_event_publisher,
        assessment,
    ):
        use_case = AddFindingUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        assessment.start()
        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.return_value = assessment

        result = await use_case.execute(
            assessment_id=assessment.id,
            requirement_code="ART-5",
            title="Missing consent mechanism",
            description="No consent mechanism implemented",
            risk_level=RiskLevel.HIGH,
            impact_score=8.0,
            likelihood_score=7.0,
        )

        assert result.status == AssessmentStatus.IN_PROGRESS
        assert len(result.findings) >= 1
        mock_assessment_repo.save.assert_called_once()

    async def test_add_finding_nonexistent_assessment(
        self,
        mock_assessment_repo,
        mock_event_publisher,
    ):
        use_case = AddFindingUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        mock_assessment_repo.get_by_id.return_value = None

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(
                assessment_id=uuid4(),
                requirement_code="ART-5",
                title="Test Finding",
                description="Test",
                risk_level=RiskLevel.LOW,
            )


class TestCompleteAssessmentUseCase:
    """Tests for CompleteAssessmentUseCase."""

    async def test_complete_assessment_success(
        self,
        mock_assessment_repo,
        mock_event_publisher,
        assessment,
    ):
        use_case = CompleteAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        assessment.start()
        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.return_value = assessment

        result = await use_case.execute(assessment.id, 85.0, uuid4())

        assert result.status == AssessmentStatus.PENDING_REVIEW
        assert result.overall_score == 85.0
        mock_assessment_repo.save.assert_called_once()

    async def test_complete_nonexistent_assessment(
        self,
        mock_assessment_repo,
        mock_event_publisher,
    ):
        use_case = CompleteAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        mock_assessment_repo.get_by_id.return_value = None

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(uuid4(), 85.0, uuid4())


class TestApproveAssessmentUseCase:
    """Tests for ApproveAssessmentUseCase."""

    async def test_approve_assessment_success(
        self,
        mock_assessment_repo,
        mock_event_publisher,
        assessment,
    ):
        use_case = ApproveAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        assessment.start()
        assessment.complete(92.0)
        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.return_value = assessment

        result = await use_case.execute(assessment.id, uuid4())

        assert result.status == AssessmentStatus.COMPLETED
        assert result.overall_score == 92.0
        mock_assessment_repo.save.assert_called_once()

    async def test_approve_nonexistent_assessment(
        self,
        mock_assessment_repo,
        mock_event_publisher,
    ):
        use_case = ApproveAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
            event_publisher=mock_event_publisher,
        )

        mock_assessment_repo.get_by_id.return_value = None

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(uuid4(), uuid4())


class TestGetAssessmentUseCase:
    """Tests for GetAssessmentUseCase."""

    async def test_get_existing_assessment(
        self,
        mock_assessment_repo,
        assessment,
    ):
        use_case = GetAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
        )

        mock_assessment_repo.get_by_id.return_value = assessment

        result = await use_case.execute(assessment.id)

        assert result.id == assessment.id
        assert result.title == assessment.title

    async def test_get_nonexistent_assessment(
        self,
        mock_assessment_repo,
    ):
        use_case = GetAssessmentUseCase(
            assessment_repo=mock_assessment_repo,
        )

        mock_assessment_repo.get_by_id.return_value = None

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(uuid4())


class TestListAssessmentsUseCase:
    """Tests for ListAssessmentsUseCase."""

    async def test_list_assessments(
        self,
        mock_assessment_repo,
        assessment,
    ):
        use_case = ListAssessmentsUseCase(
            assessment_repo=mock_assessment_repo,
        )

        mock_assessment_repo.search.return_value = ([assessment], 1)

        results, total = await use_case.execute()

        assert len(results) == 1
        assert total == 1
        assert results[0].id == assessment.id

    async def test_list_assessments_empty(
        self,
        mock_assessment_repo,
    ):
        use_case = ListAssessmentsUseCase(
            assessment_repo=mock_assessment_repo,
        )

        mock_assessment_repo.search.return_value = ([], 0)

        results, total = await use_case.execute()

        assert len(results) == 0
        assert total == 0
