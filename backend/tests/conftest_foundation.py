"""Pytest fixtures for the Enterprise Foundation layer."""

import pytest

from regulaforge.application.ports.cache import CachePort
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.unit_of_work import UnitOfWork
from regulaforge.application.services.event_bus import EventBus
from regulaforge.application.services.scheduler import TaskScheduler
from regulaforge.config.container import Container
from regulaforge.testing.base import FakeCache, FakeEventPublisher, FakeUnitOfWork


@pytest.fixture
def event_bus() -> EventBus:
    """Provide a fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def scheduler() -> TaskScheduler:
    """Provide a fresh TaskScheduler instance."""
    return TaskScheduler()


@pytest.fixture
def fake_publisher() -> FakeEventPublisher:
    """Provide a FakeEventPublisher instance."""
    return FakeEventPublisher()


@pytest.fixture
def fake_cache() -> FakeCache:
    """Provide a FakeCache instance."""
    return FakeCache()


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    """Provide a FakeUnitOfWork instance."""
    return FakeUnitOfWork()


@pytest.fixture
def container(
    fake_publisher: FakeEventPublisher,
    fake_cache: FakeCache,
    fake_uow: FakeUnitOfWork,
) -> Container:
    """Provide a pre-configured DI container containing fake implementations."""
    c = Container()
    c.register_instance(EventPublisher, fake_publisher)
    c.register_instance(CachePort, fake_cache)
    c.register_instance(UnitOfWork, fake_uow)
    return c
