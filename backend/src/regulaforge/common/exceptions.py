"""Centralized application exception hierarchy.

All RegulaForge exceptions inherit from ``RegulaForgeError``, providing
a consistent structure for error handling, logging, and API responses.

Exception hierarchy::

    RegulaForgeError
    ├── ConfigurationError
    ├── RepositoryError
    │   ├── EntityNotFoundError
    │   └── DuplicateEntityError
    ├── AuthenticationError
    ├── AuthorizationError
    ├── RateLimitError
    ├── ServiceUnavailableError
    ├── ValidationError
    ├── ExternalServiceError
    │   ├── AIServiceError
    │   ├── LLMProviderError
    │   └── EventPublishError
    ├── RetryExhaustedError
    └── CircuitBreakerOpenError
"""

from typing import Any, Optional


class RegulaForgeError(Exception):
    """Base exception for all RegulaForge application errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        cause: Optional[Exception] = None,
        *,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.details = details
        self.cause = cause
        super().__init__(message)

    @property
    def message(self) -> str:
        return self.args[0] if self.args else ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


class ConfigurationError(RegulaForgeError):
    """Raised when application configuration is invalid or missing."""

    def __init__(
        self,
        message: str = "Invalid configuration",
        *,
        code: str = "CONFIGURATION_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details, cause=cause)


class RepositoryError(RegulaForgeError):
    """Base exception for data access/repository errors."""

    def __init__(
        self,
        message: str = "A database error occurred",
        cause: Optional[Exception] = None,
        *,
        code: str = "DATABASE_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, cause, code=code, status_code=status_code, details=details)


class EntityNotFoundError(RepositoryError):
    """Raised when a requested entity does not exist."""

    def __init__(
        self,
        entity_type: str = "Entity",
        entity_id: Optional[Any] = None,
        *,
        code: str = "NOT_FOUND",
        status_code: int = 404,
        details: Optional[Any] = None,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = str(entity_id) if entity_id is not None else None
        if entity_id is not None:
            message = f"{entity_type} not found: {entity_id}"
        else:
            message = f"{entity_type} not found"
        super().__init__(message, code=code, status_code=status_code, details=details)


class DuplicateEntityError(RepositoryError):
    """Raised when attempting to create a duplicate entity."""

    def __init__(
        self,
        entity_type: str = "Entity",
        field: str = "id",
        value: Optional[Any] = None,
        *,
        code: str = "DUPLICATE_ENTITY",
        status_code: int = 409,
        details: Optional[Any] = None,
    ) -> None:
        self.entity_type = entity_type
        self.field = field
        self.value = str(value) if value is not None else None
        if value is not None:
            message = f"{entity_type} with {field} '{value}' already exists"
        else:
            message = f"{entity_type} with that {field} already exists"
        super().__init__(message, code=code, status_code=status_code, details=details)


class AuthenticationError(RegulaForgeError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        code: str = "AUTHENTICATION_ERROR",
        status_code: int = 401,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details)


class AuthorizationError(RegulaForgeError):
    """Raised when the user lacks permission for an action."""

    def __init__(
        self,
        message: str = "Permission denied",
        *,
        code: str = "FORBIDDEN",
        status_code: int = 403,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details)


class RateLimitError(RegulaForgeError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        *,
        code: str = "RATE_LIMIT_EXCEEDED",
        status_code: int = 429,
        details: Optional[Any] = None,
        retry_after: int = 60,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, code=code, status_code=status_code, details=details)


class ServiceUnavailableError(RegulaForgeError):
    """Raised when a required service is unavailable."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        *,
        code: str = "SERVICE_UNAVAILABLE",
        status_code: int = 503,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details)


class ValidationError(RegulaForgeError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        code: str = "VALIDATION_ERROR",
        status_code: int = 422,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details)


class ExternalServiceError(RegulaForgeError):
    """Base exception for external service call failures."""

    def __init__(
        self,
        message: str = "External service error",
        cause: Optional[Exception] = None,
        *,
        service_name: str = "unknown",
        code: str = "EXTERNAL_SERVICE_ERROR",
        status_code: int = 502,
        details: Optional[Any] = None,
    ) -> None:
        self.service_name = service_name
        super().__init__(message, cause, code=code, status_code=status_code, details=details)


class AIServiceError(ExternalServiceError):
    """Raised when an AI/ML service fails."""

    def __init__(
        self,
        message: str = "AI service error",
        cause: Optional[Exception] = None,
        *,
        code: str = "AI_SERVICE_ERROR",
        status_code: int = 502,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message, cause, service_name="ai", code=code, status_code=status_code,
            details=details,
        )


class LLMProviderError(ExternalServiceError):
    """Raised when the LLM provider returns an error."""

    def __init__(
        self,
        message: str = "LLM provider error",
        cause: Optional[Exception] = None,
        *,
        provider: str = "llm",
        code: str = "LLM_PROVIDER_ERROR",
        status_code: int = 502,
        details: Optional[Any] = None,
    ) -> None:
        self.provider = provider
        super().__init__(
            message, cause, service_name=provider, code=code, status_code=status_code,
            details=details,
        )


class EventPublishError(ExternalServiceError):
    """Raised when event publishing fails."""

    def __init__(
        self,
        message: str = "Failed to publish event",
        cause: Optional[Exception] = None,
        *,
        code: str = "EVENT_PUBLISH_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message, cause, service_name="event_bus", code=code, status_code=status_code,
            details=details,
        )


class RetryExhaustedError(RegulaForgeError):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str = "All retry attempts exhausted",
        *,
        code: str = "RETRY_EXHAUSTED",
        status_code: int = 503,
        details: Optional[Any] = None,
        attempts: int = 0,
    ) -> None:
        self.attempts = attempts
        super().__init__(message, code=code, status_code=status_code, details=details)


class CircuitBreakerOpenError(RegulaForgeError):
    """Raised when a circuit breaker is open and refusing requests."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        *,
        code: str = "CIRCUIT_BREAKER_OPEN",
        status_code: int = 503,
        details: Optional[Any] = None,
        retry_after: float = 30.0,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, code=code, status_code=status_code, details=details)


class ForbiddenError(AuthorizationError):
    """Raised when the user lacks permission for an action."""

    def __init__(
        self,
        message: str = "Access denied",
        *,
        code: str = "FORBIDDEN",
        status_code: int = 403,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details)


class NotFoundError(RegulaForgeError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        *,
        code: str = "NOT_FOUND",
        status_code: int = 404,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details)


class ConflictError(RegulaForgeError):
    """Raised when a conflict occurs (e.g. duplicate)."""

    def __init__(
        self,
        message: str = "Conflict",
        *,
        code: str = "CONFLICT",
        status_code: int = 409,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code, details=details)


__all__ = [
    "RegulaForgeError",
    "ConfigurationError",
    "RepositoryError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "AuthenticationError",
    "AuthorizationError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ServiceUnavailableError",
    "ValidationError",
    "ExternalServiceError",
    "AIServiceError",
    "LLMProviderError",
    "EventPublishError",
    "RetryExhaustedError",
    "CircuitBreakerOpenError",
]
