"""Shared test fixtures and configuration."""

from datetime import date, datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest
from regulaforge.config.constants import (
    AssessmentStatus,
    EntityType,
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
    RiskLevel,
)
from regulaforge.domain.entities.compliance_assessment import (
    ComplianceAssessment,
    ComplianceFinding,
)
from regulaforge.domain.entities.entity import AssessableEntity
from regulaforge.domain.entities.regulation import Regulation, RegulationRequirement

# ---------------------------------------------------------------------------
# Fixtures: Regulations
# ---------------------------------------------------------------------------

@pytest.fixture
def regulation_data() -> Dict[str, Any]:
    """Standard regulation data for tests."""
    return {
        "title": "General Data Protection Regulation",
        "code": "GDPR",
        "description": "EU regulation on data protection and privacy",
        "category": RegulationCategory.DATA_PROTECTION,
        "jurisdiction": RegulationJurisdiction.EU,
        "issuing_body": "European Parliament",
        "effective_date": date(2018, 5, 25),
        "status": RegulationStatus.ACTIVE,
    }


@pytest.fixture
def regulation(regulation_data: Dict[str, Any]) -> Regulation:
    """Create a standard regulation entity for tests."""
    reg = Regulation(**regulation_data)
    reg.add_requirement(RegulationRequirement(
        code="ART-5",
        title="Lawful processing",
        description="Personal data shall be processed lawfully, fairly and transparently",
        is_mandatory=True,
        risk_weight=1.0,
    ))
    reg.add_requirement(RegulationRequirement(
        code="ART-17",
        title="Right to erasure",
        description="Data subject has the right to erasure of personal data",
        is_mandatory=True,
        risk_weight=0.9,
    ))
    return reg


# ---------------------------------------------------------------------------
# Fixtures: Entities
# ---------------------------------------------------------------------------

@pytest.fixture
def entity_data() -> Dict[str, Any]:
    """Standard entity data for tests."""
    return {
        "name": "Acme Corporation",
        "entity_type": EntityType.ORGANIZATION,
        "tenant_id": uuid4(),
        "description": "A multinational corporation",
    }


@pytest.fixture
def entity(entity_data: Dict[str, Any]) -> AssessableEntity:
    """Create a standard entity for tests."""
    return AssessableEntity(**entity_data)


# ---------------------------------------------------------------------------
# Fixtures: Assessments
# ---------------------------------------------------------------------------

@pytest.fixture
def assessment_data(regulation: Regulation, entity: AssessableEntity) -> Dict[str, Any]:
    """Standard assessment data for tests."""
    return {
        "title": "GDPR Compliance Assessment 2024",
        "entity_id": entity.id,
        "entity_type": entity.entity_type.value,
        "regulation_ids": [regulation.id],
        "assessor_id": uuid4(),
        "due_date": date(2024, 12, 31),
        "status": AssessmentStatus.SCHEDULED,
    }


@pytest.fixture
def assessment(assessment_data: Dict[str, Any]) -> ComplianceAssessment:
    """Create a standard assessment for tests."""
    return ComplianceAssessment(**assessment_data)


# ---------------------------------------------------------------------------
# Fixtures: Findings
# ---------------------------------------------------------------------------

@pytest.fixture
def finding_data() -> Dict[str, Any]:
    """Standard finding data for tests."""
    return {
        "requirement_code": "ART-5",
        "title": "Missing consent mechanism",
        "description": "No consent mechanism implemented for data processing",
        "risk_level": RiskLevel.HIGH,
        "impact_score": 8.0,
        "likelihood_score": 7.0,
        "remediation_recommendation": "Implement consent management platform",
    }


@pytest.fixture
def finding(finding_data: Dict[str, Any]) -> ComplianceFinding:
    """Create a standard finding for tests."""
    return ComplianceFinding(**finding_data)


# ---------------------------------------------------------------------------
# Fixtures: Use Cases
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_regulation_repo(mocker):
    """Mock regulation repository."""
    return mocker.AsyncMock()


@pytest.fixture
def mock_assessment_repo(mocker):
    """Mock assessment repository."""
    return mocker.AsyncMock()


@pytest.fixture
def mock_entity_repo(mocker):
    """Mock entity repository."""
    return mocker.AsyncMock()


@pytest.fixture
def mock_event_publisher(mocker):
    """Mock event publisher."""
    publisher = mocker.AsyncMock()
    return publisher
