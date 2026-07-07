"""Unified testing base classes, fakes, and utilities."""

import fnmatch
import inspect
from abc import ABC
from datetime import datetime, timezone
import pytest
from types import TracebackType
from typing import Any, Generic, Optional, Type, TypeVar
import uuid
from uuid import UUID

from regulaforge.application.ports.cache import CachePort
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.repository import SearchableRepository, EntityNotFoundError
from regulaforge.application.ports.unit_of_work import UnitOfWork
from regulaforge.domain.entities.base import DomainEntity
from regulaforge.domain.events.base import DomainEvent

T = TypeVar("T", bound=DomainEntity)


class InMemoryRepository(SearchableRepository[T], Generic[T]):
    """Generic in-memory repository implementation for unit testing."""

    def __init__(self) -> None:
        self.entities: dict[UUID, T] = {}

    async def save(self, entity: T) -> T:
        self.entities[entity.id] = entity
        return entity

    async def get_by_id(self, entity_id: UUID) -> Optional[T]:
        return self.entities.get(entity_id)

    async def delete(self, entity_id: UUID) -> None:
        if entity_id not in self.entities:
            raise EntityNotFoundError("Entity", entity_id)
        del self.entities[entity_id]

    async def exists(self, entity_id: UUID) -> bool:
        return entity_id in self.entities

    async def count(self, filters: Optional[dict[str, object]] = None) -> int:
        filtered = self._apply_filters(filters)
        return len(filtered)

    async def search(
        self,
        filters: Optional[dict[str, object]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[T], int]:
        filtered = self._apply_filters(filters)
        
        if sort_by:
            def sort_key(x: T) -> Any:
                val = getattr(x, sort_by, None)
                if val is None and hasattr(x, f"_{sort_by}"):
                    val = getattr(x, f"_{sort_by}")
                return val if val is not None else ""
            
            filtered.sort(key=sort_key, reverse=(sort_order.lower() == "desc"))

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    def _apply_filters(self, filters: Optional[dict[str, object]]) -> list[T]:
        if not filters:
            return list(self.entities.values())
        
        results = []
        for entity in self.entities.values():
            match = True
            for key, val in filters.items():
                attr_val = getattr(entity, key, None)
                if attr_val is None and hasattr(entity, f"_{key}"):
                    attr_val = getattr(entity, f"_{key}")
                if attr_val != val:
                    match = False
                    break
            if match:
                results.append(entity)
        return results


class FakeEventPublisher(EventPublisher):
    """Fake event publisher that collects published events in-memory."""

    def __init__(self) -> None:
        self.published_events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published_events.append(event)

    async def publish_batch(self, events: list[DomainEvent]) -> None:
        self.published_events.extend(events)

    async def publish_delayed(self, event: DomainEvent, delay_seconds: int) -> None:
        self.published_events.append(event)


class FakeCache(CachePort):
    """Fake in-memory cache implementation."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.store

    async def get_many(self, *keys: str) -> dict[str, str]:
        return {k: self.store[k] for k in keys if k in self.store}

    async def invalidate_pattern(self, pattern: str) -> int:
        count = 0
        for key in list(self.store.keys()):
            if fnmatch.fnmatchcase(key, pattern):
                del self.store[key]
                count += 1
        return count


class FakeUnitOfWork(UnitOfWork):
    """Fake Unit of Work with in-memory repositories."""

    def __init__(self) -> None:
        self._regulations = InMemoryRepository()
        self._assessments = InMemoryRepository()
        self._entities = InMemoryRepository()
        self._documents = InMemoryRepository()
        self._users = InMemoryRepository()
        self._roles = InMemoryRepository()
        self.committed = False
        self.rolled_back = False
        self.tracked_entities: list[DomainEntity] = []

    @property
    def regulations(self) -> InMemoryRepository:
        return self._regulations

    @property
    def assessments(self) -> InMemoryRepository:
        return self._assessments

    @property
    def entities(self) -> InMemoryRepository:
        return self._entities

    @property
    def documents(self) -> InMemoryRepository:
        return self._documents

    @property
    def users(self) -> InMemoryRepository:
        return self._users

    @property
    def roles(self) -> InMemoryRepository:
        return self._roles

    def track(self, entity: DomainEntity) -> None:
        self.tracked_entities.append(entity)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        return None


def create_test_entity(cls: Type[T], **overrides: Any) -> T:
    """Helper to instantiate a domain entity with sensible default values."""
    sig = inspect.signature(cls.__init__)
    kwargs = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "args", "kwargs"):
            continue
        if param_name in overrides:
            kwargs[param_name] = overrides[param_name]
        elif param.default is not inspect.Parameter.empty:
            kwargs[param_name] = param.default
        elif param.annotation == uuid.UUID or param.annotation == "UUID":
            kwargs[param_name] = uuid.uuid4()
        elif param.annotation == datetime or param.annotation == "datetime":
            kwargs[param_name] = datetime.now(timezone.utc)
        elif param.annotation == str:
            kwargs[param_name] = f"test_{param_name}"
        elif param.annotation == int:
            kwargs[param_name] = 1
        elif param.annotation == bool:
            kwargs[param_name] = False
        else:
            kwargs[param_name] = None
    
    for k, v in overrides.items():
        if k not in kwargs:
            kwargs[k] = v

    return cls(**kwargs)


class BaseUnitTest:
    """Base class for unit tests providing standard test setup."""

    @pytest.fixture(autouse=True)
    def setup_unit_test(self) -> None:
        pass


class BaseIntegrationTest:
    """Base class for integration tests."""

    @pytest.fixture(autouse=True)
    def setup_integration_test(self) -> None:
        pass
