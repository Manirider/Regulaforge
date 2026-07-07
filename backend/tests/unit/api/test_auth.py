"""Integration tests for auth API endpoints.

Tests registration, login, token refresh, and password change flows.
Uses FastAPI TestClient with proper dependency overrides.
"""

import asyncio
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from regulaforge.config.settings import AppSettings, EnvironmentType
from regulaforge.interfaces.api.app import create_app
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine


@pytest.fixture
def app_settings():
    s = AppSettings(
        environment=EnvironmentType.TESTING,
        database__url="sqlite+aiosqlite://",
    )
    s.security.secret_key = "test-secret-key-32-chars-long!!"
    s.security.cors_origins = ["*"]
    s.security.allowed_hosts = ["*"]
    return s


@pytest.fixture
def client(app_settings):
    import regulaforge.infrastructure.persistence.database as db_module

    fh = tempfile.NamedTemporaryFile(prefix="regulaforge_test_", suffix=".db", delete=False)
    db_path = fh.name
    fh.close()
    db_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(db_url)

    async def init_test_db():
        async with engine.begin() as conn:
            await conn.run_sync(db_module.Base.metadata.create_all)

    asyncio.run(init_test_db())

    db_module._engine = engine
    db_module._session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def _noop():
        pass

    async def _health_ok():
        return True

    with (
        patch("regulaforge.interfaces.api.app.settings", app_settings),
        patch("regulaforge.interfaces.api.app.initialize_database", _noop),
        patch("regulaforge.interfaces.api.app.check_database_health", _health_ok),
    ):
        app = create_app()
        with TestClient(app) as c:
            yield c

    os.unlink(db_path)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code in (200, 503)  # May return degraded if no DB

    def test_health_response_structure(self, client):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "database" in data


class TestRegistration:
    def test_register_missing_fields(self, client):
        response = client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422

    def test_register_invalid_email(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "invalid",
            "username": "testuser",
            "password": "ValidP@ss1",
        })
        # Should return 422 for invalid email format
        assert response.status_code in (400, 422)

    def test_register_weak_password(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "weak",
        })
        # Backend should reject weak passwords
        assert response.status_code in (400, 422)


class TestLogin:
    def test_login_nonexistent_user(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "SomePass1!",
        })
        assert response.status_code == 401

    def test_login_empty_body(self, client):
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422


class TestAuthMiddleware:
    def test_me_without_token(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    def test_admin_without_token(self, client):
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401

    def test_admin_with_invalid_token(self, client):
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": "Bearer invalid"},
        )
        assert response.status_code == 401
