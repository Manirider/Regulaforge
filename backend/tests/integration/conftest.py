"""Integration test fixtures with mock repositories and FastAPI test client."""

import asyncio
from datetime import date, datetime, timezone
from typing import Any, AsyncGenerator, Dict, List
from uuid import UUID, uuid4

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.adapters.assessment_repository_adapter import (
    SqlAlchemyAssessmentRepository,
)
from regulaforge.infrastructure.persistence.adapters.regulation_repository_adapter import (
    SqlAlchemyRegulationRepository,
)
from regulaforge.infrastructure.persistence.adapters.user_repository_adapter import (
    SqlAlchemyUserRepository,
)
from regulaforge.interfaces.api.app import create_app
from regulaforge.interfaces.api.dependencies import (
    get_add_finding_uc,
    get_add_requirement_uc,
    get_approve_assessment_uc,
    get_assessment_repo,
    get_change_password_uc,
    get_complete_assessment_uc,
    get_create_assessment_uc,
    get_create_regulation_uc,
    get_entity_repo,
    get_event_publisher,
    get_get_assessment_uc,
    get_get_regulation_uc,
    get_list_assessments_uc,
    get_login_uc,
    get_publish_regulation_uc,
    get_refresh_uc,
    get_register_uc,
    get_regulation_repo,
    get_role_repo,
    get_search_regulations_uc,
    get_start_assessment_uc,
    get_user_repo,
)


@pytest.fixture
def mock_regulation_repo(mocker):
    return mocker.AsyncMock()


@pytest.fixture
def mock_assessment_repo(mocker):
    return mocker.AsyncMock()


@pytest.fixture
def mock_entity_repo(mocker):
    return mocker.AsyncMock()


@pytest.fixture
def mock_event_publisher(mocker):
    publisher = mocker.AsyncMock()
    return publisher


@pytest.fixture
def regulation_data() -> Dict[str, Any]:
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


@pytest.fixture
def draft_regulation_data() -> Dict[str, Any]:
    return {
        "title": "New Data Protection Regulation",
        "code": "NDPR",
        "description": "A new regulation in draft status",
        "category": RegulationCategory.DATA_PROTECTION,
        "jurisdiction": RegulationJurisdiction.EU,
        "issuing_body": "European Parliament",
        "effective_date": date(2025, 1, 1),
    }


@pytest.fixture
def entity_data() -> Dict[str, Any]:
    return {
        "name": "Acme Corporation",
        "entity_type": EntityType.ORGANIZATION,
        "tenant_id": uuid4(),
        "description": "A multinational corporation",
    }


@pytest.fixture
def entity(entity_data: Dict[str, Any]) -> AssessableEntity:
    return AssessableEntity(**entity_data)


@pytest.fixture
def assessment_data(regulation: Regulation, entity: AssessableEntity) -> Dict[str, Any]:
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
    return ComplianceAssessment(**assessment_data)


@pytest.fixture
def finding_data() -> Dict[str, Any]:
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
def mock_user_repo(mocker):
    return mocker.AsyncMock()


@pytest.fixture
def mock_role_repo(mocker):
    return mocker.AsyncMock()


@pytest.fixture
def mock_current_user(mock_user_repo) -> Any:
    from regulaforge.domain.entities.user import User
    from regulaforge.infrastructure.security.password_service import PasswordService

    pw_hash = PasswordService().hash_password("StrongPass1!")
    return User(
        email="test@example.com",
        username="testuser",
        password_hash=pw_hash,
        full_name="Test User",
    )


@pytest.fixture
def test_app(
    mock_regulation_repo,
    mock_assessment_repo,
    mock_entity_repo,
    mock_event_publisher,
    mock_user_repo,
    mock_role_repo,
    mock_current_user,
) -> Any:
    from regulaforge.interfaces.api.middleware.auth_middleware import (
        get_current_user,
    )

    from regulaforge.config.settings import settings as global_settings
    global_settings.security.allowed_hosts = ["*"]

    app = create_app()
    app.root_path = ""
    app.dependency_overrides = {}

    app.dependency_overrides[get_regulation_repo] = lambda: mock_regulation_repo
    app.dependency_overrides[get_assessment_repo] = lambda: mock_assessment_repo
    app.dependency_overrides[get_entity_repo] = lambda: mock_entity_repo
    app.dependency_overrides[get_event_publisher] = lambda: mock_event_publisher
    app.dependency_overrides[get_user_repo] = lambda: mock_user_repo
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo

    async def _mock_get_current_user() -> Any:
        return mock_current_user

    app.dependency_overrides[get_current_user] = _mock_get_current_user

    return app


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def seeded_regulation_id() -> UUID:
    return uuid4()


@pytest.fixture
def seed_regulation(
    mock_regulation_repo,
    regulation: Regulation,
    seeded_regulation_id: UUID,
) -> Regulation:
    reg = regulation
    reg._id = seeded_regulation_id
    mock_regulation_repo.get_by_id.return_value = reg
    mock_regulation_repo.get_by_code.return_value = None
    mock_regulation_repo.save.return_value = reg
    return reg


@pytest.fixture
def seeded_draft_regulation(
    mock_regulation_repo,
    draft_regulation_data: Dict[str, Any],
) -> Regulation:
    reg = Regulation(**draft_regulation_data)
    mock_regulation_repo.get_by_id.return_value = reg
    mock_regulation_repo.save.return_value = reg
    return reg


# ---------------------------------------------------------------------------
# Real database fixtures for repository integration tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_engine():
    """Module-scoped SQLite in-memory engine with tables created once."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init())
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped async session backed by the module-scoped engine."""
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    session = factory()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def user_repo(db_session: AsyncSession) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session=db_session)


@pytest.fixture
async def regulation_repo(db_session: AsyncSession) -> SqlAlchemyRegulationRepository:
    return SqlAlchemyRegulationRepository(session=db_session)


@pytest.fixture
async def assessment_repo(db_session: AsyncSession) -> SqlAlchemyAssessmentRepository:
    return SqlAlchemyAssessmentRepository(session=db_session)
