"""Tests for application settings validation and security defaults."""

import os
from typing import Generator

import pytest
from regulaforge.config.settings import AppSettings, EnvironmentType


class TestAppSettingsDefaults:
    def test_default_environment_is_development(self):
        settings = AppSettings()
        assert settings.environment == EnvironmentType.DEVELOPMENT

    def test_default_security_rejects_short_key(self):
        import pydantic
        from regulaforge.config.settings import SecurityConfig
        with pytest.raises((ValueError, pydantic.ValidationError)):
            SecurityConfig(secret_key="short")

    def test_cors_not_wildcard_in_production(self):
        """In production, CORS should be explicit."""
        settings = AppSettings(
            environment=EnvironmentType.PRODUCTION,
            security__secret_key="a-32-char-secret-key-for-testing!!",
        )
        # Production should not use wildcard CORS
        cors = settings.security.cors_origins
        assert cors != ["*"], "Production CORS must not be wildcard"

    def test_allowed_hosts_not_wildcard_in_production(self):
        settings = AppSettings(
            environment=EnvironmentType.PRODUCTION,
            security__secret_key="a-32-char-secret-key-for-testing!!",
        )
        hosts = settings.security.allowed_hosts
        assert hosts != ["*"], "Production allowed_hosts must not be wildcard"

    def test_log_level_info_in_production(self):
        settings = AppSettings(
            environment=EnvironmentType.PRODUCTION,
            security__secret_key="a-32-char-secret-key-for-testing!!",
        )
        assert settings.log_level.value == "INFO"


class TestDatabaseConfig:
    def test_default_pool_size(self):
        settings = AppSettings(security__secret_key="a-32-char-secret-key-for-testing!!")
        assert settings.database.pool_size >= 1

    def test_custom_database_url(self):
        settings = AppSettings(
            database__url="postgresql+asyncpg://user:pass@host:5432/db",
            security__secret_key="a-32-char-secret-key-for-testing!!",
        )
        assert "host" in str(settings.database.url)


class TestAIConfig:
    def test_default_model(self):
        settings = AppSettings(security__secret_key="a-32-char-secret-key-for-testing!!")
        assert settings.ai.llm_model == "gpt-4-turbo"
        assert settings.ai.enable_hallucination_detection is True


class TestSetSettings:
    def test_set_settings_overrides(self):
        from regulaforge.config.settings import set_settings

        original = AppSettings(security__secret_key="a-32-char-secret-key-for-testing!!")
        set_settings(original)
        from regulaforge.config.settings import settings
        assert settings.environment == original.environment

        # Reset
        set_settings(AppSettings(security__secret_key="a-32-char-secret-key-for-testing!!"))


class TestRiskEngineConfig:
    def test_default_thresholds(self):
        settings = AppSettings(security__secret_key="a-32-char-secret-key-for-testing!!")
        assert settings.risk_engine.risk_score_thresholds["critical"] == 80
        assert settings.risk_engine.risk_score_thresholds["low"] == 20
