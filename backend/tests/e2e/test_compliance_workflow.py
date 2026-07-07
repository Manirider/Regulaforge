"""End-to-end compliance workflow test.

Tests the complete lifecycle: create entity -> create regulation ->
create assessment -> start -> add findings -> complete -> approve,
verifying the final compliance level using the real API stack with SQLite.
"""

from uuid import uuid4

import pytest
from regulaforge.config.constants import (
    AssessmentStatus,
    ComplianceLevel,
    EntityType,
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
)

pytestmark = pytest.mark.e2e


class TestComplianceWorkflow:
    """Complete E2E compliance assessment workflow."""

    async def _create_entity(self, client) -> dict:
        payload = {
            "name": "Acme Corporation",
            "entity_type": EntityType.ORGANIZATION.value,
            "tenant_id": str(uuid4()),
            "description": "A multinational corporation subject to GDPR compliance",
        }
        response = await client.post("/api/v1/entities", json=payload)
        assert response.status_code == 201
        return response.json()

    async def _create_regulation(self, client) -> dict:
        payload = {
            "title": "General Data Protection Regulation",
            "code": "GDPR",
            "description": "EU regulation on data protection and privacy",
            "category": RegulationCategory.DATA_PROTECTION.value,
            "jurisdiction": RegulationJurisdiction.EU.value,
            "issuing_body": "European Parliament",
            "effective_date": "2018-05-25",
        }
        response = await client.post("/api/v1/regulations", json=payload)
        assert response.status_code == 201
        return response.json()

    async def _publish_regulation(self, client, regulation_id: str) -> dict:
        response = await client.post(f"/api/v1/regulations/{regulation_id}/publish")
        assert response.status_code == 200
        return response.json()

    async def _add_requirement(self, client, regulation_id: str) -> dict:
        payload = {
            "code": "ART-5",
            "title": "Lawful processing",
            "description": "Personal data shall be processed lawfully, fairly and transparently",
            "is_mandatory": True,
            "risk_weight": 1.0,
        }
        response = await client.post(
            f"/api/v1/regulations/{regulation_id}/requirements",
            json=payload,
        )
        assert response.status_code == 200
        return response.json()

    async def _create_assessment(self, client, entity_id: str, regulation_id: str) -> dict:
        payload = {
            "title": "GDPR Compliance Assessment 2024",
            "entity_id": entity_id,
            "regulation_ids": [regulation_id],
            "assessor_id": str(uuid4()),
            "due_date": "2024-12-31",
        }
        response = await client.post("/api/v1/assessments", json=payload)
        assert response.status_code == 201
        return response.json()

    async def _start_assessment(self, client, assessment_id: str) -> dict:
        response = await client.post(f"/api/v1/assessments/{assessment_id}/start")
        assert response.status_code == 200
        return response.json()

    async def _add_finding(self, client, assessment_id: str) -> dict:
        payload = {
            "requirement_code": "ART-5",
            "title": "Missing consent mechanism",
            "description": "No consent mechanism implemented for data processing",
            "risk_level": "high",
            "impact_score": 8.0,
            "likelihood_score": 7.0,
            "remediation_recommendation": "Implement consent management platform",
        }
        response = await client.post(
            f"/api/v1/assessments/{assessment_id}/findings",
            json=payload,
        )
        assert response.status_code == 200
        return response.json()

    async def _complete_assessment(self, client, assessment_id: str) -> dict:
        payload = {"score": 92.0}
        response = await client.post(
            f"/api/v1/assessments/{assessment_id}/complete",
            json=payload,
        )
        assert response.status_code == 200
        return response.json()

    async def _approve_assessment(self, client, assessment_id: str) -> dict:
        response = await client.post(f"/api/v1/assessments/{assessment_id}/approve")
        assert response.status_code == 200
        return response.json()

    async def test_complete_compliance_workflow(self, async_client):
        # Step 1: Create an entity
        entity = await self._create_entity(async_client)
        assert entity["name"] == "Acme Corporation"
        assert entity["is_active"] is True
        assert "id" in entity

        # Step 2: Create a regulation
        regulation = await self._create_regulation(async_client)
        assert regulation["title"] == "General Data Protection Regulation"
        assert regulation["code"] == "GDPR"
        assert regulation["status"] == RegulationStatus.DRAFT.value

        # Step 3: Publish the regulation
        published = await self._publish_regulation(async_client, regulation["id"])
        assert published["status"] == RegulationStatus.ACTIVE.value

        # Step 4: Add a requirement to the regulation
        req_result = await self._add_requirement(async_client, regulation["id"])
        assert len(req_result["requirements"]) >= 1

        # Step 5: Create an assessment
        assessment = await self._create_assessment(
            async_client,
            entity["id"],
            regulation["id"],
        )
        assert assessment["title"] == "GDPR Compliance Assessment 2024"
        assert assessment["status"] == AssessmentStatus.SCHEDULED.value

        # Step 6: Start the assessment
        started = await self._start_assessment(async_client, assessment["id"])
        assert started["status"] == AssessmentStatus.IN_PROGRESS.value

        # Step 7: Add findings
        with_finding = await self._add_finding(async_client, assessment["id"])
        assert with_finding["status"] == AssessmentStatus.IN_PROGRESS.value
        assert len(with_finding["findings"]) >= 1

        # Step 8: Complete the assessment
        completed = await self._complete_assessment(async_client, assessment["id"])
        assert completed["status"] == AssessmentStatus.PENDING_REVIEW.value
        assert completed["overall_score"] == 92.0
        assert completed["compliance_level"] == ComplianceLevel.FULLY_COMPLIANT.value

        # Step 9: Approve the assessment
        approved = await self._approve_assessment(async_client, assessment["id"])
        assert approved["status"] == AssessmentStatus.COMPLETED.value
        assert approved["overall_score"] == 92.0
        assert approved["compliance_level"] == ComplianceLevel.FULLY_COMPLIANT.value
        assert approved["approved_by"] is not None
        assert approved["approved_at"] is not None
        assert approved["completed_at"] is not None

        # Step 10: Verify via GET endpoint
        response = await async_client.get(f"/api/v1/assessments/{assessment['id']}")
        assert response.status_code == 200
        final = response.json()
        assert final["status"] == AssessmentStatus.COMPLETED.value
        assert final["overall_score"] == 92.0
        assert final["compliance_level"] == ComplianceLevel.FULLY_COMPLIANT.value
