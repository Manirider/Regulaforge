"""Application configuration management.

Uses pydantic-settings for environment-aware, validated configuration
following the 12-factor app methodology. All secrets must be provided
via environment variables or a .env file (never committed to VCS).
"""

from __future__ import annotations

import os
import warnings
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import (
    AmqpDsn,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentType(str, Enum):
    """Deployment environment enumeration."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ─── Sub-configurations ──────────────────────────────────────────────


class DatabaseConfig(BaseSettings):
    """Database connection configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_DB_",
        env_file=".env",
        extra="ignore",
    )

    url: PostgresDsn | str = Field(
        default="postgresql+asyncpg://regulaforge:regulaforge@localhost:5432/regulaforge",
        description="PostgreSQL connection string with async driver",
    )
    pool_size: int = Field(default=20, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, description="Maximum pool overflow connections")
    pool_recycle: int = Field(default=3600, ge=60, description="Connection recycle time (seconds)")
    echo: bool = Field(default=False, description="SQL statement logging")
    migrate_on_startup: bool = Field(default=True, description="Run migrations on startup")


class CacheConfig(BaseSettings):
    """Redis cache configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_CACHE_",
        env_file=".env",
        extra="ignore",
    )

    url: RedisDsn = Field(
        default=RedisDsn("redis://localhost:6379/0"),
        description="Redis connection string",
    )
    default_ttl: int = Field(default=300, ge=1, description="Default cache TTL (seconds)")
    max_connections: int = Field(default=10, ge=1, description="Maximum pool connections")


class MessageBrokerConfig(BaseSettings):
    """Message broker (RabbitMQ) configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_BROKER_",
        env_file=".env",
        extra="ignore",
    )

    url: AmqpDsn = Field(
        default=AmqpDsn("amqp://guest:guest@localhost:5672/"),
        description="AMQP connection string",
    )
    max_retries: int = Field(default=3, ge=0, description="Maximum delivery retries")
    prefetch_count: int = Field(default=10, ge=1, description="Consumer prefetch count")


class AIConfig(BaseSettings):
    """AI/ML service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_AI_",
        env_file=".env",
        extra="ignore",
    )

    llm_provider: str = Field(default="openai", description="LLM provider (openai, anthropic, azure)")
    llm_model: str = Field(default="gpt-4-turbo", description="Default LLM model")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM temperature")
    llm_max_tokens: int = Field(default=4096, ge=1, description="Maximum LLM response tokens")
    embedding_model: str = Field(default="text-embedding-3-large", description="Embedding model name")
    embedding_dimensions: int = Field(default=1536, ge=128, description="Embedding vector dimensions")
    confidence_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="Minimum confidence for AI predictions",
    )
    enable_explainability: bool = Field(default=True, description="Enable AI explainability features")
    enable_hallucination_detection: bool = Field(
        default=True, description="Enable hallucination detection",
    )
    max_chunk_size: int = Field(default=4096, ge=256, description="Max document chunk size for processing")


class SecurityConfig(BaseSettings):
    """Security and authentication configuration.

    REGULAFORGE_SECURITY_SECRET_KEY must be set in production via environment variable.
    """

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_SECURITY_",
        env_file=".env",
        extra="ignore",
    )

    secret_key: SecretStr = Field(
        default=SecretStr("dev-secret-key-change-in-prod-12345678!"),
        description="JWT signing secret (min 32 chars). MUST be set via environment in production.",
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(default=30, ge=1, description="Access token TTL")
    refresh_token_expire_days: int = Field(default=7, ge=1, description="Refresh token TTL")
    bcrypt_rounds: int = Field(default=12, ge=4, le=20, description="BCrypt cost factor")
    allowed_hosts: list[str] = Field(
        default=["localhost", "127.0.0.1", "api.regulaforge.example.com"],
        description="Allowed hosts",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins",
    )
    rate_limit_per_minute: int = Field(default=60, ge=1, description="API rate limit per minute")
    max_login_attempts: int = Field(default=5, ge=1, description="Max failed login attempts before lockout")
    lockout_duration_minutes: int = Field(default=15, ge=1, description="Account lockout duration")
    session_timeout_minutes: int = Field(default=60, ge=1, description="Session idle timeout")
    csp_enabled: bool = Field(default=True, description="Enable Content-Security-Policy header")
    csp_directives: str = Field(default="", description="Custom CSP directives (overrides defaults)")
    hsts_enabled: bool = Field(default=True, description="Enable HSTS header in production")
    hsts_max_age: int = Field(default=31536000, ge=0, description="HSTS max-age in seconds")

    @model_validator(mode="after")
    def validate_secrets(self) -> SecurityConfig:
        secret_value = self.secret_key.get_secret_value()
        if len(secret_value) < 32:
            raise ValueError(
                "REGULAFORGE_SECURITY_SECRET_KEY must be at least 32 characters. "
                "This is a SECURITY REQUIREMENT."
            )
        if self.cors_origins == ["*"]:
            warnings.warn(
                "CORS is set to '*' — dangerous in production. "
                "Set REGULAFORGE_SECURITY_CORS_ORIGINS.",
                stacklevel=2,
            )
        return self


class Neo4jConfig(BaseSettings):
    """Neo4j graph database connection configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_NEO4J_",
        env_file=".env",
        extra="ignore",
    )

    uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    user: str = Field(default="neo4j", description="Neo4j username")
    password: SecretStr = Field(default=SecretStr("regulaforge"), description="Neo4j password")
    database: str = Field(default="regulaforge", description="Neo4j database name")
    max_connection_pool_size: int = Field(default=50, ge=1, le=200, description="Max connection pool size")
    connection_timeout: int = Field(default=30, ge=1, description="Connection timeout (seconds)")


class RiskEngineConfig(BaseSettings):
    """Risk Prediction Engine configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_RISK_",
        env_file=".env",
        extra="ignore",
    )

    risk_score_thresholds: dict[str, float] = Field(
        default={"critical": 80, "high": 60, "medium": 40, "low": 20},
        description="Risk score thresholds for severity classification",
    )
    risk_prediction_model: str = Field(
        default="compliance_classifier",
        description="ML model name for risk prediction",
    )
    risk_confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Minimum confidence for ML-based risk predictions",
    )
    risk_monitoring_interval_seconds: int = Field(
        default=300, ge=10,
        description="Interval between risk monitoring cycles",
    )
    risk_trend_lookback_days: int = Field(
        default=90, ge=1, le=365,
        description="Default lookback period for risk trend analysis",
    )
    risk_alert_auto_resolve_days: int = Field(
        default=30, ge=1,
        description="Days after which unresolved alerts auto-resolve",
    )


class SentryConfig(BaseSettings):
    """Sentry error tracking configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_SENTRY_",
        env_file=".env",
        extra="ignore",
    )

    dsn: Optional[str] = Field(default=None, description="Sentry DSN")
    traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Traces sample rate")
    profiles_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Profiles sample rate")
    environment: Optional[str] = Field(default=None, description="Override Sentry environment name")


class OpenTelemetryConfig(BaseSettings):
    """OpenTelemetry distributed tracing configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_OTEL_",
        env_file=".env",
        extra="ignore",
    )

    enabled: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otlp_endpoint: Optional[str] = Field(default=None, description="OTLP collector endpoint")
    otlp_headers: Optional[str] = Field(default=None, description="OTLP headers (comma-separated key=value)")
    service_name: str = Field(default="regulaforge", description="OTel service name")
    sample_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Trace sample rate")


class MonitoringConfig(BaseSettings):
    """Observability and monitoring configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_MONITORING_",
        env_file=".env",
        extra="ignore",
    )

    enable_prometheus: bool = Field(default=True, description="Enable Prometheus metrics")
    health_check_interval: int = Field(default=30, ge=5, description="Health check interval (seconds)")


class IngestionConfig(BaseSettings):
    """Regulatory document ingestion configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_INGESTION_",
        env_file=".env",
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Enable ingestion pipeline")
    raw_storage_path: Path = Field(
        default=Path("/data/regulaforge/ingestion/raw"),
        description="Raw downloaded file storage path",
    )
    text_storage_path: Path = Field(
        default=Path("/data/regulaforge/ingestion/text"),
        description="Extracted text storage path",
    )
    metadata_storage_path: Path = Field(
        default=Path("/data/regulaforge/ingestion/metadata"),
        description="Document metadata storage path",
    )
    versions_storage_path: Path = Field(
        default=Path("/data/regulaforge/ingestion/versions"),
        description="Version history storage path",
    )

    max_concurrent_downloads: int = Field(default=5, ge=1, le=50, description="Max concurrent downloads")
    download_timeout_seconds: int = Field(default=120, ge=30, description="Download timeout (seconds)")
    retry_max_attempts: int = Field(default=3, ge=0, le=10, description="Max download retry attempts")
    retry_base_delay: float = Field(default=1.0, ge=0.1, description="Retry base delay (seconds)")
    retry_max_delay: float = Field(default=60.0, ge=1.0, description="Retry max delay (seconds)")

    scheduler_enabled: bool = Field(default=True, description="Enable automatic crawl scheduler")
    rbi_crawl_interval_minutes: int = Field(default=60, ge=15, description="RBI crawl interval (minutes)")
    sebi_crawl_interval_minutes: int = Field(default=120, ge=15, description="SEBI crawl interval (minutes)")
    irdai_crawl_interval_minutes: int = Field(default=180, ge=15, description="IRDAI crawl interval (minutes)")

    dedup_simhash_threshold: float = Field(default=0.85, ge=0.5, le=1.0, description="Simhash similarity threshold for dedup")
    enable_hash_verification: bool = Field(default=True, description="Verify file hashes on download")
    enable_auto_etl: bool = Field(default=True, description="Auto-run ETL pipeline after download")

    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics for ingestion")
    batch_size: int = Field(default=100, ge=10, le=1000, description="Repository batch size")
    cleanup_after_days: int = Field(default=90, ge=1, description="Days before cleaning up old temp files")


# ─── Root settings ──────────────────────────────────────────────────


class AppSettings(BaseSettings):
    """Root application settings aggregating all sub-configurations."""

    model_config = SettingsConfigDict(
        env_prefix="REGULAFORGE_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # Application metadata
    app_name: str = Field(default="RegulaForge", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    description: str = Field(
        default="Enterprise AI Compliance Platform",
        description="Application description",
    )
    environment: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Deployment environment",
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_json: bool = Field(default=True, description="Use JSON log formatting")
    timezone: str = Field(default="UTC", description="Application timezone")

    # API configuration
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    api_prefix: str = Field(default="/api/v1", description="API version prefix")
    docs_enabled: bool = Field(default=True, description="Enable Swagger/OpenAPI docs")
    openapi_url: str = Field(default="/api/v1/openapi.json", description="OpenAPI schema URL")
    max_request_size: int = Field(default=10_485_760, ge=1, description="Max request body size (10MB)")

    # Secrets provider
    secrets_provider: str = Field(default="env", description="Secrets provider backend (env|aws|vault|azure)")

    # Storage paths
    data_dir: Path = Field(default=Path("/data/regulaforge"), description="Data directory")
    upload_dir: Path = Field(default=Path("/data/regulaforge/uploads"), description="Upload directory")
    model_dir: Path = Field(default=Path("/data/regulaforge/models"), description="Model storage directory")
    temp_dir: Path = Field(default=Path("/tmp/regulaforge"), description="Temporary file directory")

    # Sub-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    broker: MessageBrokerConfig = Field(default_factory=MessageBrokerConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    risk_engine: RiskEngineConfig = Field(default_factory=RiskEngineConfig)
    sentry: SentryConfig = Field(default_factory=SentryConfig)
    otel: OpenTelemetryConfig = Field(default_factory=OpenTelemetryConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)

    # ------------------------------------------------------------------
    # Convenience properties (delegate to sub-configs)
    # ------------------------------------------------------------------

    @property
    def risk_score_thresholds(self) -> dict[str, float]:
        return self.risk_engine.risk_score_thresholds

    @property
    def risk_confidence_threshold(self) -> float:
        return self.risk_engine.risk_confidence_threshold

    def is_development(self) -> bool:
        return self.environment == EnvironmentType.DEVELOPMENT

    def is_production(self) -> bool:
        return self.environment == EnvironmentType.PRODUCTION

    def is_testing(self) -> bool:
        return self.environment == EnvironmentType.TESTING

    @model_validator(mode="before")
    @classmethod
    def handle_double_underscore_kwargs(cls, values: Any) -> Any:
        if isinstance(values, dict):
            for key, val in list(values.items()):
                if "__" in key:
                    parts = key.split("__", 1)
                    prefix, subkey = parts[0], parts[1]
                    nested = values.get(prefix)
                    if nested is None:
                        nested = {}
                    elif not isinstance(nested, dict):
                        if hasattr(nested, "__dict__"):
                            nested = dict(nested)
                        else:
                            nested = {}
                    nested[subkey] = val
                    values[prefix] = nested
                    values.pop(key, None)
        return values

    @model_validator(mode="after")
    def validate_production_secrets(self) -> AppSettings:
        if self.is_production():
            try:
                sec = self.security.secret_key.get_secret_value()
            except Exception:
                sec = ""
            if not sec or sec == "dev-secret-key-change-in-prod-12345678!":
                raise ValueError(
                    "REGULAFORGE_SECURITY_SECRET_KEY must be set to a strong, "
                    "unique value in production. The development default is not acceptable."
                )
        return self


settings = AppSettings()
"""Global application settings singleton."""


def set_settings(new_settings: AppSettings) -> None:
    """Override the global settings singleton."""
    global settings
    for field_name in settings.model_fields:
        if hasattr(new_settings, field_name):
            val = getattr(new_settings, field_name)
            try:
                object.__setattr__(settings, field_name, val)
            except AttributeError:
                pass
    settings = new_settings


__all__ = [
    "EnvironmentType",
    "LogLevel",
    "DatabaseConfig",
    "CacheConfig",
    "MessageBrokerConfig",
    "AIConfig",
    "SecurityConfig",
    "Neo4jConfig",
    "RiskEngineConfig",
    "SentryConfig",
    "OpenTelemetryConfig",
    "MonitoringConfig",
    "IngestionConfig",
    "AppSettings",
    "settings",
    "set_settings",
]
