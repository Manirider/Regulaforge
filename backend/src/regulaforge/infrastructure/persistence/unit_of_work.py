"""SQLAlchemy implementation of the Unit of Work port."""

from types import TracebackType
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.unit_of_work import UnitOfWork
from regulaforge.domain.entities.base import DomainEntity
from regulaforge.infrastructure.persistence.adapters.assessment_repository_adapter import (
    SqlAlchemyAssessmentRepository,
)
from regulaforge.infrastructure.persistence.adapters.document_repository_adapter import (
    SqlAlchemyDocumentRepository,
)
from regulaforge.infrastructure.persistence.adapters.entity_repository_adapter import (
    SqlAlchemyEntityRepository,
)
from regulaforge.infrastructure.persistence.adapters.regulation_repository_adapter import (
    SqlAlchemyRegulationRepository,
)
from regulaforge.infrastructure.persistence.adapters.role_repository_adapter import (
    SqlAlchemyRoleRepository,
)
from regulaforge.infrastructure.persistence.adapters.user_repository_adapter import (
    SqlAlchemyUserRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of UnitOfWork.

    Manages transaction lifecycle and uses repository adapters.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_publisher: Optional[EventPublisher] = None,
    ) -> None:
        self._session_factory = session_factory
        self._event_publisher = event_publisher
        self._session: Optional[AsyncSession] = None
        self._tracked_entities: list[DomainEntity] = []

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self._tracked_entities = []
        self._session.info["tracked_entities"] = self._tracked_entities
        # Instantiate repositories using the active session
        self._regulations = SqlAlchemyRegulationRepository(self._session)
        self._assessments = SqlAlchemyAssessmentRepository(self._session)
        self._entities = SqlAlchemyEntityRepository(self._session)
        self._documents = SqlAlchemyDocumentRepository(self._session)
        self._users = SqlAlchemyUserRepository(self._session)
        self._roles = SqlAlchemyRoleRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            if self._session:
                await self._session.close()
                self._session = None
        return None

    @property
    def regulations(self) -> SqlAlchemyRegulationRepository:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        return self._regulations

    @property
    def assessments(self) -> SqlAlchemyAssessmentRepository:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        return self._assessments

    @property
    def entities(self) -> SqlAlchemyEntityRepository:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        return self._entities

    @property
    def documents(self) -> SqlAlchemyDocumentRepository:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        return self._documents

    @property
    def users(self) -> SqlAlchemyUserRepository:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        return self._users

    @property
    def roles(self) -> SqlAlchemyRoleRepository:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        return self._roles

    def track(self, entity: DomainEntity) -> None:
        """Register a domain entity for event collection."""
        if entity not in self._tracked_entities:
            self._tracked_entities.append(entity)

    async def commit(self) -> None:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        
        await self._session.commit()
        await self._dispatch_events()

    async def rollback(self) -> None:
        if not self._session:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        await self._session.rollback()
        self._tracked_entities.clear()

    async def _dispatch_events(self) -> None:
        if not self._event_publisher:
            self._tracked_entities.clear()
            return

        events = []
        for entity in self._tracked_entities:
            events.extend(entity.clear_events())
        
        self._tracked_entities.clear()

        if events:
            await self._event_publisher.publish_batch(events)
