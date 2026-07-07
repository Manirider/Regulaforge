"""Common utilities, exceptions, validation, and shared types for RegulaForge.

This package provides the foundational building blocks used across all
layers of the application:
  - ``exceptions``: Centralized exception hierarchy
  - ``types``: Shared type aliases and protocols
  - ``validation``: Reusable validation utilities built on Pydantic
  - ``utils``: General-purpose utilities (retry, timing, singletons)
  - ``patterns``: Design pattern helpers (registry, observable, circuit-breaker)
"""

from regulaforge.common.exceptions import (
    RegulaForgeError,
    ConfigurationError,
    RepositoryError,
    EntityNotFoundError,
    DuplicateEntityError,
    AuthenticationError,
    AuthorizationError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError as AppValidationError,
    ExternalServiceError,
    AIServiceError,
    EventPublishError,
    LLMProviderError,
    RetryExhaustedError,
    CircuitBreakerOpenError,
)

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
    "AppValidationError",
    "ExternalServiceError",
    "AIServiceError",
    "EventPublishError",
    "LLMProviderError",
    "RetryExhaustedError",
    "CircuitBreakerOpenError",
]
