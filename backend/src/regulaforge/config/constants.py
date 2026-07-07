"""Application-wide constants and enumerations.

Centralizes all magic strings, numeric constants, and domain enumerations
to ensure consistency across the codebase and simplify maintenance.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT_REQUESTS: Final[int] = 15
DEFAULT_RATE_LIMIT_WINDOW_SECONDS: Final[int] = 60
AUTH_RATE_LIMIT_REQUESTS: Final[int] = 5
AUTH_RATE_LIMIT_WINDOW_SECONDS: Final[int] = 60
ML_RATE_LIMIT_REQUESTS: Final[int] = 30
ML_RATE_LIMIT_WINDOW_SECONDS: Final[int] = 60

# ---------------------------------------------------------------------------
# Password Policy
# ---------------------------------------------------------------------------

PASSWORD_MIN_LENGTH: Final[int] = 12
PASSWORD_MAX_LENGTH: Final[int] = 128
MAX_PASSWORD_LENGTH: Final[int] = PASSWORD_MAX_LENGTH
MIN_PASSWORD_LENGTH: Final[int] = PASSWORD_MIN_LENGTH
PASSWORD_REQUIRE_UPPERCASE: Final[bool] = True
PASSWORD_REQUIRE_LOWERCASE: Final[bool] = True
PASSWORD_REQUIRE_DIGIT: Final[bool] = True
PASSWORD_REQUIRE_SPECIAL: Final[bool] = True
PASSWORD_BCRYPT_ROUNDS: Final[int] = 12

# ---------------------------------------------------------------------------
# Cache Duration
# ---------------------------------------------------------------------------

TENANT_CACHE_TTL: Final[int] = 300       # 5 minutes
USER_CACHE_TTL: Final[int] = 60          # 1 minute
ASSESSMENT_CACHE_TTL: Final[int] = 120   # 2 minutes
REGULATION_CACHE_TTL: Final[int] = 600   # 10 minutes
DOCUMENT_CACHE_TTL: Final[int] = 120     # 2 minutes
ENTITY_CACHE_TTL: Final[int] = 300       # 5 minutes

# ---------------------------------------------------------------------------
# File Size Limits
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE_MB: Final[int] = 100
MAX_UPLOAD_SIZE_BYTES: Final[int] = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ALLOWED_UPLOAD_EXTENSIONS: Final[tuple[str, ...]] = (
    ".pdf", ".docx", ".doc", ".xlsx", ".xls",
    ".csv", ".json", ".xml", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".tiff",
)

# ---------------------------------------------------------------------------
# Region / Currency / Language Enums
# ---------------------------------------------------------------------------


class Region(str, Enum):
    US = "us"
    EU = "eu"
    UK = "uk"
    APAC = "apac"
    GLOBAL = "global"


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"


class Language(str, Enum):
    EN = "en"
    FR = "fr"
    DE = "de"
    ES = "es"
    IT = "it"
    JA = "ja"
    ZH = "zh"


# ---------------------------------------------------------------------------
# API Constants
# ---------------------------------------------------------------------------

API_V1_PREFIX: Final[str] = "/api/v1"
API_TITLE: Final[str] = "RegulaForge API"
API_DESCRIPTION: Final[str] = (
    "Enterprise-grade RESTful API for AI-powered regulatory compliance management. "
    "Provides regulation ingestion, compliance assessment, audit logging, "
    "and intelligent reporting capabilities."
)
API_VERSION: Final[str] = "0.1.0"
API_CONTACT_NAME: Final[str] = "RegulaForge Engineering"
API_CONTACT_EMAIL: Final[str] = "engineering@regulaforge.io"
API_CONTACT_URL: Final[str] = "https://regulaforge.io"

# HTTP Status Codes (descriptive names)
HTTP_200_OK: Final[int] = 200
HTTP_201_CREATED: Final[int] = 201
HTTP_204_NO_CONTENT: Final[int] = 204
HTTP_400_BAD_REQUEST: Final[int] = 400
HTTP_401_UNAUTHORIZED: Final[int] = 401
HTTP_403_FORBIDDEN: Final[int] = 403
HTTP_404_NOT_FOUND: Final[int] = 404
HTTP_409_CONFLICT: Final[int] = 409
HTTP_422_UNPROCESSABLE_ENTITY: Final[int] = 422
HTTP_429_TOO_MANY_REQUESTS: Final[int] = 429
HTTP_500_INTERNAL_SERVER_ERROR: Final[int] = 500
HTTP_503_SERVICE_UNAVAILABLE: Final[int] = 503

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100
DEFAULT_PAGE: Final[int] = 1

# ---------------------------------------------------------------------------
# Domain Enumerations (re-exported from domain.enums for backward compat)
# ---------------------------------------------------------------------------

from regulaforge.domain.enums import (  # noqa: E402
    ArtifactType,
    AssessmentStatus,
    AuditAction,
    ComplianceLevel,
    EntityType,
    EventType,
    NotificationChannel,
    NotificationPriority,
    PromptTemplateType,
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
    RiskLevel,
)

# ---------------------------------------------------------------------------
# Business Rules
# ---------------------------------------------------------------------------

COMPLIANCE_PASS_THRESHOLD: Final[int] = 80       # percentage
CRITICAL_FINDING_THRESHOLD: Final[int] = 5       # max critical findings before auto-escalation
MAX_DOCUMENT_PAGES: Final[int] = 500
MAX_BATCH_SIZE: Final[int] = 100
MAX_RETRY_ATTEMPTS: Final[int] = 3

# Cache keys
CACHE_KEY_REGULATION: Final[str] = "regulation:{id}"
CACHE_KEY_ASSESSMENT: Final[str] = "assessment:{id}"
CACHE_KEY_TENANT_CONFIG: Final[str] = "tenant:{id}:config"
CACHE_KEY_USER_PERMISSIONS: Final[str] = "user:{id}:permissions"
CACHE_KEY_ENTITY: Final[str] = "entity:{id}"
CACHE_TTL_REGULATION: Final[int] = 3600
CACHE_TTL_ASSESSMENT: Final[int] = 300
CACHE_TTL_TENANT_CONFIG: Final[int] = 600
CACHE_TTL_USER_PERMISSIONS: Final[int] = 1800

# Messaging
DEFAULT_EXCHANGE: Final[str] = "regulaforge"
DLQ_SUFFIX: Final[str] = ".dlq"
RETRY_SUFFIX: Final[str] = ".retry"
MAX_RETRY_DELAY_SECONDS: Final[int] = 3600


__all__ = [
    # Rate limiting
    "DEFAULT_RATE_LIMIT_REQUESTS",
    "DEFAULT_RATE_LIMIT_WINDOW_SECONDS",
    "AUTH_RATE_LIMIT_REQUESTS",
    "AUTH_RATE_LIMIT_WINDOW_SECONDS",
    "ML_RATE_LIMIT_REQUESTS",
    "ML_RATE_LIMIT_WINDOW_SECONDS",
    # Password policy
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_REQUIRE_UPPERCASE",
    "PASSWORD_REQUIRE_LOWERCASE",
    "PASSWORD_REQUIRE_DIGIT",
    "PASSWORD_REQUIRE_SPECIAL",
    "PASSWORD_BCRYPT_ROUNDS",
    # Cache duration
    "TENANT_CACHE_TTL",
    "USER_CACHE_TTL",
    "ASSESSMENT_CACHE_TTL",
    "REGULATION_CACHE_TTL",
    "DOCUMENT_CACHE_TTL",
    "ENTITY_CACHE_TTL",
    # File size limits
    "MAX_UPLOAD_SIZE_MB",
    "MAX_UPLOAD_SIZE_BYTES",
    "ALLOWED_UPLOAD_EXTENSIONS",
    # Enums
    "Region",
    "Currency",
    "Language",
    # API
    "API_V1_PREFIX",
    "API_TITLE",
    "API_DESCRIPTION",
    "API_VERSION",
    "API_CONTACT_NAME",
    "API_CONTACT_EMAIL",
    "API_CONTACT_URL",
    # HTTP Status
    "HTTP_200_OK",
    "HTTP_201_CREATED",
    "HTTP_204_NO_CONTENT",
    "HTTP_400_BAD_REQUEST",
    "HTTP_401_UNAUTHORIZED",
    "HTTP_403_FORBIDDEN",
    "HTTP_404_NOT_FOUND",
    "HTTP_409_CONFLICT",
    "HTTP_422_UNPROCESSABLE_ENTITY",
    "HTTP_429_TOO_MANY_REQUESTS",
    "HTTP_500_INTERNAL_SERVER_ERROR",
    "HTTP_503_SERVICE_UNAVAILABLE",
    # Pagination
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "DEFAULT_PAGE",
    # Domain enums
    "RegulationStatus",
    "RegulationCategory",
    "RegulationJurisdiction",
    "ComplianceLevel",
    "RiskLevel",
    "EntityType",
    "ArtifactType",
    "AssessmentStatus",
    "NotificationPriority",
    "NotificationChannel",
    "AuditAction",
    "PromptTemplateType",
    "EventType",
    # Business rules
    "COMPLIANCE_PASS_THRESHOLD",
    "CRITICAL_FINDING_THRESHOLD",
    "MAX_DOCUMENT_PAGES",
    "MAX_BATCH_SIZE",
    "MAX_RETRY_ATTEMPTS",
    # Cache keys
    "CACHE_KEY_REGULATION",
    "CACHE_KEY_ASSESSMENT",
    "CACHE_KEY_TENANT_CONFIG",
    "CACHE_KEY_USER_PERMISSIONS",
    "CACHE_KEY_ENTITY",
    "CACHE_TTL_REGULATION",
    "CACHE_TTL_ASSESSMENT",
    "CACHE_TTL_TENANT_CONFIG",
    "CACHE_TTL_USER_PERMISSIONS",
    # Messaging
    "DEFAULT_EXCHANGE",
    "DLQ_SUFFIX",
    "RETRY_SUFFIX",
    "MAX_RETRY_DELAY_SECONDS",
]
