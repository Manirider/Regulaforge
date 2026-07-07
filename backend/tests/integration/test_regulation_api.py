"""Integration tests for regulation API endpoints.

Tests the API routing, request validation, response serialization,
and error handling for all regulation endpoints with mocked repositories.
"""

from datetime import date
from uuid import UUID, uuid4

import pytest
from regulaforge.config.constants import (
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
)
from regulaforge.domain.repositories.base import DuplicateEntityError, EntityNotFoundError

pytestmark = pytest.mark.integration


class TestCreateRegulationViaApi:
    """POST /api/v1/regulations"""

    async def test_create_regulation_via_api(
        self, async_client, mock_regulation_repo, regulation_data
    ):
        mock_regulation_repo.get_by_code.return_value = None
        mock_regulation_repo.save.side_effect = lambda reg: reg

        payload = {
            "title": regulation_data["title"],
            "code": regulation_data["code"],
            "description": regulation_data["description"],
            "category": regulation_data["category"].value,
            "jurisdiction": regulation_data["jurisdiction"].value,
            "issuing_body": regulation_data["issuing_body"],
            "effective_date": regulation_data["effective_date"].isoformat(),
        }

        response = await async_client.post("/api/v1/regulations", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == regulation_data["title"]
        assert data["code"] == regulation_data["code"]
        assert "id" in data
        assert data["status"] == RegulationStatus.DRAFT.value
        mock_regulation_repo.get_by_code.assert_called_once_with("GDPR")

    async def test_create_duplicate_regulation_via_api(
        self, async_client, mock_regulation_repo, regulation_data
    ):
        mock_regulation_repo.get_by_code.return_value = True

        payload = {
            "title": regulation_data["title"],
            "code": regulation_data["code"],
            "description": regulation_data["description"],
            "category": regulation_data["category"].value,
            "jurisdiction": regulation_data["jurisdiction"].value,
            "issuing_body": regulation_data["issuing_body"],
            "effective_date": regulation_data["effective_date"].isoformat(),
        }

        response = await async_client.post("/api/v1/regulations", json=payload)

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    async def test_create_regulation_missing_required_fields(self, async_client):
        payload = {"title": "Incomplete Regulation"}

        response = await async_client.post("/api/v1/regulations", json=payload)

        assert response.status_code == 422


class TestGetRegulationViaApi:
    """GET /api/v1/regulations/{id}"""

    async def test_get_regulation_via_api(
        self, async_client, seed_regulation, seeded_regulation_id
    ):
        response = await async_client.get(f"/api/v1/regulations/{seeded_regulation_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "General Data Protection Regulation"
        assert data["code"] == "GDPR"
        assert data["status"] == RegulationStatus.ACTIVE.value
        assert "requirements" in data

    async def test_get_nonexistent_regulation_via_api(
        self, async_client, mock_regulation_repo
    ):
        nonexistent_id = uuid4()
        mock_regulation_repo.get_by_id.return_value = None

        response = await async_client.get(f"/api/v1/regulations/{nonexistent_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestListRegulationsViaApi:
    """GET /api/v1/regulations"""

    async def test_list_regulations_via_api(
        self, async_client, mock_regulation_repo, regulation
    ):
        mock_regulation_repo.search.return_value = ([regulation], 1)

        response = await async_client.get("/api/v1/regulations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "General Data Protection Regulation"

    async def test_list_regulations_empty(
        self, async_client, mock_regulation_repo
    ):
        mock_regulation_repo.search.return_value = ([], 0)

        response = await async_client.get("/api/v1/regulations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    async def test_list_regulations_with_filters(
        self, async_client, mock_regulation_repo, regulation
    ):
        mock_regulation_repo.search.return_value = ([regulation], 1)

        response = await async_client.get(
            "/api/v1/regulations",
            params={"status": "active", "category": "data_protection", "page": 1, "page_size": 10},
        )

        assert response.status_code == 200


class TestPublishRegulationViaApi:
    """POST /api/v1/regulations/{id}/publish"""

    async def test_publish_regulation_via_api(
        self, async_client, seeded_draft_regulation, mock_regulation_repo
    ):
        draft = seeded_draft_regulation
        mock_regulation_repo.get_by_id.return_value = draft
        mock_regulation_repo.save.side_effect = lambda reg: reg

        response = await async_client.post(f"/api/v1/regulations/{draft.id}/publish")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == RegulationStatus.ACTIVE.value

    async def test_publish_nonexistent_regulation(
        self, async_client, mock_regulation_repo
    ):
        mock_regulation_repo.get_by_id.return_value = None
        nonexistent_id = uuid4()

        response = await async_client.post(f"/api/v1/regulations/{nonexistent_id}/publish")

        assert response.status_code == 404


class TestAddRequirementViaApi:
    """POST /api/v1/regulations/{id}/requirements"""

    async def test_add_requirement_via_api(
        self, async_client, seed_regulation, seeded_regulation_id, mock_regulation_repo
    ):
        mock_regulation_repo.save.return_value = seed_regulation

        payload = {
            "code": "ART-32",
            "title": "Security of processing",
            "description": "Implement appropriate technical and organizational measures",
            "is_mandatory": True,
            "risk_weight": 0.95,
        }

        response = await async_client.post(
            f"/api/v1/regulations/{seeded_regulation_id}/requirements",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "General Data Protection Regulation"

    async def test_add_requirement_nonexistent_regulation(
        self, async_client, mock_regulation_repo
    ):
        mock_regulation_repo.get_by_id.return_value = None
        nonexistent_id = uuid4()

        payload = {
            "code": "ART-99",
            "title": "Test Requirement",
            "description": "A test requirement",
        }

        response = await async_client.post(
            f"/api/v1/regulations/{nonexistent_id}/requirements",
            json=payload,
        )

        assert response.status_code == 404
