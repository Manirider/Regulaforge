"""Port interfaces for the application layer.

Ports define the contracts that adapters (inbound and outbound)
must implement, enabling hexagonal architecture.

Available ports:
- auth: IAuthTokenService, IPasswordService, TokenPayload
- event_publisher: EventPublisher
- llm_provider: LLMProvider
- repository: BaseRepository, SearchableRepository, RepositoryError
"""

from regulaforge.application.ports.auth import IAuthTokenService, IPasswordService, TokenPayload
from regulaforge.application.ports.cache import CachePort
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.llm_provider import LLMProvider
from regulaforge.application.ports.repository import (
    BaseRepository,
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
    SearchableRepository,
)
from regulaforge.application.ports.unit_of_work import UnitOfWork

__all__ = [
    "IAuthTokenService",
    "IPasswordService",
    "TokenPayload",
    "CachePort",
    "EventPublisher",
    "LLMProvider",
    "BaseRepository",
    "SearchableRepository",
    "RepositoryError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "UnitOfWork",
]
