"""Integration tests for assessment API endpoints.

Tests the API routing, request validation, response serialization,
and error handling for all assessment endpoints with mocked repositories.
"""

from datetime import date
from uuid import UUID, uuid4

import pytest
from regulaforge.config.constants import (
    AssessmentStatus,
    ComplianceLevel,
    EntityType,
    RiskLevel,
)
from regulaforge.domain.entities.compliance_assessment import ComplianceAssessment
from regulaforge.domain.repositories.base import EntityNotFoundError

pytestmark = pytest.mark.integration


class TestCreateAssessmentViaApi:
    """POST /api/v1/assessments"""

    async def test_create_assessment_via_api(
        self, async_client, mock_entity_repo, mock_regulation_repo,
        mock_assessment_repo, entity, regulation,
    ):
        mock_entity_repo.get_by_id.return_value = entity
        mock_regulation_repo.get_by_id.return_value = regulation
        mock_assessment_repo.save.return_value = ComplianceAssessment(
            title="GDPR Compliance Assessment 2024",
            entity_id=entity.id,
            entity_type=entity.entity_type.value,
            regulation_ids=[regulation.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
        )

        payload = {
            "title": "GDPR Compliance Assessment 2024",
            "entity_id": str(entity.id),
            "regulation_ids": [str(regulation.id)],
            "assessor_id": str(uuid4()),
            "due_date": "2024-12-31",
        }

        response = await async_client.post("/api/v1/assessments", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "GDPR Compliance Assessment 2024"
        assert data["status"] == AssessmentStatus.SCHEDULED.value
        assert "id" in data

    async def test_create_assessment_with_nonexistent_entity(
        self, async_client, mock_entity_repo, mock_regulation_repo, regulation,
    ):
        mock_entity_repo.get_by_id.return_value = None
        mock_regulation_repo.get_by_id.return_value = regulation

        payload = {
            "title": "Assessment with bad entity",
            "entity_id": str(uuid4()),
            "regulation_ids": [str(regulation.id)],
            "assessor_id": str(uuid4()),
            "due_date": "2024-12-31",
        }

        response = await async_client.post("/api/v1/assessments", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_create_assessment_missing_title(self, async_client, entity, regulation):
        payload = {
            "entity_id": str(entity.id),
            "regulation_ids": [str(regulation.id)],
            "assessor_id": str(uuid4()),
            "due_date": "2024-12-31",
        }

        response = await async_client.post("/api/v1/assessments", json=payload)

        assert response.status_code == 422


class TestGetAssessmentViaApi:
    """GET /api/v1/assessments/{id}"""

    async def test_get_assessment_via_api(
        self, async_client, mock_assessment_repo, assessment,
    ):
        mock_assessment_repo.get_by_id.return_value = assessment

        response = await async_client.get(f"/api/v1/assessments/{assessment.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == assessment.title
        assert data["status"] == AssessmentStatus.SCHEDULED.value
        assert str(data["entity_id"]) == str(assessment.entity_id)

    async def test_get_nonexistent_assessment_via_api(
        self, async_client, mock_assessment_repo,
    ):
        mock_assessment_repo.get_by_id.return_value = None
        nonexistent_id = uuid4()

        response = await async_client.get(f"/api/v1/assessments/{nonexistent_id}")

        assert response.status_code == 404


class TestListAssessmentsViaApi:
    """GET /api/v1/assessments"""

    async def test_list_assessments_via_api(
        self, async_client, mock_assessment_repo, assessment,
    ):
        mock_assessment_repo.search.return_value = ([assessment], 1)

        response = await async_client.get("/api/v1/assessments")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == assessment.title


class TestStartAssessmentViaApi:
    """POST /api/v1/assessments/{id}/start"""

    async def test_start_assessment_via_api(
        self, async_client, mock_assessment_repo, assessment,
    ):
        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.side_effect = lambda a: a

        response = await async_client.post(f"/api/v1/assessments/{assessment.id}/start")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == AssessmentStatus.IN_PROGRESS.value

    async def test_start_nonexistent_assessment(
        self, async_client, mock_assessment_repo,
    ):
        mock_assessment_repo.get_by_id.return_value = None
        nonexistent_id = uuid4()

        response = await async_client.post(f"/api/v1/assessments/{nonexistent_id}/start")

        assert response.status_code == 404


class TestAddFindingViaApi:
    """POST /api/v1/assessments/{id}/findings"""

    async def test_add_finding_via_api(
        self, async_client, mock_assessment_repo, assessment, finding_data,
    ):
        assessment.start()
        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.return_value = assessment

        response = await async_client.post(
            f"/api/v1/assessments/{assessment.id}/findings",
            json=finding_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == AssessmentStatus.IN_PROGRESS.value

    async def test_add_finding_to_nonexistent_assessment(
        self, async_client, mock_assessment_repo, finding_data,
    ):
        mock_assessment_repo.get_by_id.return_value = None
        nonexistent_id = uuid4()

        response = await async_client.post(
            f"/api/v1/assessments/{nonexistent_id}/findings",
            json=finding_data,
        )

        assert response.status_code == 404


class TestCompleteAssessmentViaApi:
    """POST /api/v1/assessments/{id}/complete"""

    async def test_complete_assessment_via_api(
        self, async_client, mock_assessment_repo, assessment,
    ):
        assessment.start()
        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.return_value = assessment

        response = await async_client.post(
            f"/api/v1/assessments/{assessment.id}/complete",
            json={"score": 85.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == AssessmentStatus.PENDING_REVIEW.value
        assert data["overall_score"] == 85.0

    async def test_complete_nonexistent_assessment(
        self, async_client, mock_assessment_repo,
    ):
        mock_assessment_repo.get_by_id.return_value = None
        nonexistent_id = uuid4()

        response = await async_client.post(
            f"/api/v1/assessments/{nonexistent_id}/complete",
            json={"score": 85.0},
        )

        assert response.status_code == 404


class TestApproveAssessmentViaApi:
    """POST /api/v1/assessments/{id}/approve"""

    async def test_approve_assessment_via_api(
        self, async_client, mock_assessment_repo, assessment,
    ):
        assessment.start()
        assessment.complete(92.0)
        mock_assessment_repo.get_by_id.return_value = assessment
        mock_assessment_repo.save.return_value = assessment

        response = await async_client.post(
            f"/api/v1/assessments/{assessment.id}/approve",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == AssessmentStatus.COMPLETED.value
        assert data["overall_score"] == 92.0

    async def test_approve_nonexistent_assessment(
        self, async_client, mock_assessment_repo,
    ):
        mock_assessment_repo.get_by_id.return_value = None
        nonexistent_id = uuid4()

        response = await async_client.post(
            f"/api/v1/assessments/{nonexistent_id}/approve",
        )

        assert response.status_code == 404
