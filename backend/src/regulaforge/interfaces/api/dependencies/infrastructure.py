"""Infrastructure adapter dependencies."""

from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.llm_provider import LLMProvider
from regulaforge.infrastructure.external.openai_provider import OpenAIProvider
from regulaforge.infrastructure.messaging.event_publisher_adapter import LoggingEventPublisher
from regulaforge.infrastructure.security.jwt_service import JWTService
from regulaforge.infrastructure.security.password_service import PasswordService


def get_event_publisher() -> EventPublisher:
    """Provide an event publisher adapter."""
    return LoggingEventPublisher()


def get_llm_provider() -> LLMProvider:
    """Provide an LLM provider adapter."""
    return OpenAIProvider()


def get_jwt_service() -> JWTService:
    """Provide a JWT service instance."""
    return JWTService()


def get_password_service() -> PasswordService:
    """Provide a password service instance."""
    return PasswordService()
