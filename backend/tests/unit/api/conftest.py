"""Shared fixtures for unit API tests.

Provides a TestClient fixture that prevents real database
connections and overrides settings for test compatibility.
"""

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine

from regulaforge.config.settings import AppSettings, EnvironmentType
from regulaforge.interfaces.api.app import create_app


@pytest.fixture
def client():
    app_settings = AppSettings(
        environment=EnvironmentType.TESTING,
        database__url="sqlite+aiosqlite://",
    )
    app_settings.security.secret_key = "test-secret-key-32-chars-long!!"
    app_settings.security.cors_origins = ["*"]
    app_settings.security.allowed_hosts = ["*"]

    import regulaforge.infrastructure.persistence.database as db_module

    engine = create_async_engine("sqlite+aiosqlite://")

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

    with patch("regulaforge.interfaces.api.app.settings", app_settings):
        app = create_app()
        with TestClient(app) as c:
            yield c
