from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from regulaforge.domain.repositories.assessment_repository import AssessmentRepository
    from regulaforge.domain.repositories.document_repository import DocumentRepository
    from regulaforge.domain.repositories.entity_repository import EntityRepository
    from regulaforge.domain.repositories.regulation_repository import RegulationRepository
    from regulaforge.domain.repositories.role_repository import RoleRepository
    from regulaforge.domain.repositories.user_repository import UserRepository


class UnitOfWork(ABC):
    """Abstract port interface for the Unit of Work pattern.

    Coordinates transactions and dispatches domain events registered
    on entities during the transaction.
    """

    @property
    @abstractmethod
    def regulations(self) -> RegulationRepository:
        """Access the regulation repository."""
        ...

    @property
    @abstractmethod
    def assessments(self) -> AssessmentRepository:
        """Access the compliance assessment repository."""
        ...

    @property
    @abstractmethod
    def entities(self) -> EntityRepository:
        """Access the assessable entity repository."""
        ...

    @property
    @abstractmethod
    def documents(self) -> DocumentRepository:
        """Access the document repository."""
        ...

    @property
    @abstractmethod
    def users(self) -> UserRepository:
        """Access the user repository."""
        ...

    @property
    @abstractmethod
    def roles(self) -> RoleRepository:
        """Access the role repository."""
        ...

    @abstractmethod
    async def commit(self) -> None:
        """Commit the active transaction and dispatch collected domain events."""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """Roll back the active transaction."""
        ...

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        """Enter the transaction context."""
        ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Exit the transaction context."""
        ...
