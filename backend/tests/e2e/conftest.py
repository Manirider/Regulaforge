"""E2E test fixtures with in-memory SQLite database and real app stack."""

import os
from typing import Any, AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from regulaforge.infrastructure.persistence.database import Base as SQLAlchemyBase
from regulaforge.infrastructure.persistence.models.assessment_model import (
    AssessmentRegulationModel,
    ComplianceAssessmentModel,
    ComplianceFindingModel,
)
from regulaforge.infrastructure.persistence.models.entity_model import AssessableEntityModel
from regulaforge.infrastructure.persistence.models.regulation_model import (
    RegulationModel,
    RegulationRequirementModel,
)
from regulaforge.interfaces.api.app import create_app
from regulaforge.interfaces.api.dependencies import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def async_test_db():
    import tempfile
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )
    async with engine.begin() as conn:
        for table in SQLAlchemyBase.metadata.sorted_tables:
            try:
                await conn.run_sync(table.create, checkfirst=True)
            except Exception:
                pass
    try:
        yield engine
    finally:
        await engine.dispose()
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
async def test_session(async_test_db) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=async_test_db,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def mock_current_user():
    from regulaforge.domain.entities.user import User
    from regulaforge.infrastructure.security.password_service import PasswordService
    pw = PasswordService().hash_password("StrongPass1!")
    return User(
        email="test@example.com",
        username="testuser",
        password_hash=pw,
        full_name="Test User",
    )


@pytest.fixture
def test_app(mock_current_user):
    from regulaforge.config.settings import settings as global_settings
    from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user

    global_settings.security.allowed_hosts = ["*"]

    async def _mock_get_current_user() -> Any:
        return mock_current_user

    app = create_app()
    app.dependency_overrides[get_current_user] = _mock_get_current_user
    return app


@pytest.fixture
async def async_client(test_app, test_session) -> AsyncGenerator[AsyncClient, None]:
    test_app.root_path = ""

    async def override_get_db_session():
        yield test_session

    test_app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    test_app.dependency_overrides.clear()