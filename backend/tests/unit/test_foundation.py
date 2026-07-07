"""Unit tests for the Enterprise Foundation layer."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Type
import pytest
from uuid import uuid4

from regulaforge.config.environment import env_manager, Environment
from regulaforge.config.container import Container, Lifetime
from regulaforge.domain.events.base import DomainEvent
from regulaforge.domain.entities.base import DomainEntity
from regulaforge.domain.services.domain_service import DomainService
from regulaforge.application.use_cases.base import UseCase
from regulaforge.application.services.event_bus import EventBus
from regulaforge.application.services.scheduler import TaskScheduler
from regulaforge.testing.base import (
    InMemoryRepository,
    FakeEventPublisher,
    FakeCache,
    FakeUnitOfWork,
    create_test_entity,
)
from regulaforge.common.exceptions import ValidationError, ConfigurationError

# ---------------------------------------------------------------------------
# 1. Environment Manager Tests
# ---------------------------------------------------------------------------

def test_environment_manager_singleton() -> None:
    assert env_manager is not None
    # Verify singleton property
    assert env_manager is env_manager


def test_environment_manager_defaults() -> None:
    # Default config
    assert env_manager.current in (
        Environment.DEVELOPMENT,
        Environment.STAGING,
        Environment.PRODUCTION,
        Environment.TESTING,
    )
    assert isinstance(env_manager.metadata.get("hostname"), str)
    assert isinstance(env_manager.metadata.get("pid"), int)
    assert isinstance(env_manager.metadata, dict)


def test_feature_flags() -> None:
    env_manager.set_feature_flag("test_feature", True)
    assert env_manager.is_feature_enabled("test_feature") is True

    env_manager.set_feature_flag("test_feature", False)
    assert env_manager.is_feature_enabled("test_feature") is False


# ---------------------------------------------------------------------------
# 2. DI Container Tests
# ---------------------------------------------------------------------------

class DummyInterface:
    pass

class DummyImplementation(DummyInterface):
    pass

class SubDependency:
    pass

class DependentService:
    def __init__(self, dep: DummyInterface, sub: SubDependency) -> None:
        self.dep = dep
        self.sub = sub

@pytest.mark.asyncio
async def test_container_registration_and_resolution() -> None:
    c = Container()
    c.register(DummyInterface, DummyImplementation, Lifetime.TRANSIENT)
    c.register(SubDependency, SubDependency, Lifetime.SINGLETON)
    c.register(DependentService, DependentService, Lifetime.TRANSIENT)

    dep = await c.resolve(DummyInterface)
    assert isinstance(dep, DummyImplementation)

    # SubDependency is registered as a singleton
    sub1 = await c.resolve(SubDependency)
    sub2 = await c.resolve(SubDependency)
    assert sub1 is sub2

    # Auto-wiring resolution
    service = await c.resolve(DependentService)
    assert isinstance(service, DependentService)
    assert isinstance(service.dep, DummyImplementation)
    assert service.sub is sub1


@pytest.mark.asyncio
async def test_container_scopes() -> None:
    c = Container()
    c.register(DummyInterface, DummyImplementation, Lifetime.SCOPED)

    with pytest.raises(KeyError):
        # Cannot resolve SCOPED lifetime at root without a scope
        await c.resolve(DummyInterface)

    async with c.create_scope() as scope:
        dep1 = await scope.resolve(DummyInterface)
        dep2 = await scope.resolve(DummyInterface)
        assert dep1 is dep2  # Shared in the same scope

    async with c.create_scope() as scope2:
        dep3 = await scope2.resolve(DummyInterface)
        assert dep3 is not dep1  # Different scope, different instance


@pytest.mark.asyncio
async def test_container_overrides() -> None:
    c = Container()
    c.register(DummyInterface, DummyImplementation, Lifetime.TRANSIENT)

    class MockImplementation(DummyInterface):
        pass

    c.override(DummyInterface, MockImplementation)
    dep = await c.resolve(DummyInterface)
    assert isinstance(dep, MockImplementation)

    c.clear_overrides()
    dep2 = await c.resolve(DummyInterface)
    assert isinstance(dep2, DummyImplementation)


# ---------------------------------------------------------------------------
# 3. Domain Event & Domain Entity Tests
# ---------------------------------------------------------------------------

class SampleEntity(DomainEntity):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = name


def test_domain_entity_base_features() -> None:
    tenant_id = uuid4()
    entity = SampleEntity(name="Acme", tenant_id=tenant_id)

    assert entity.tenant_id == tenant_id
    assert entity.is_deleted is False
    assert entity.deleted_at is None

    # Soft delete
    entity.mark_deleted()
    assert entity.is_deleted is True
    assert isinstance(entity.deleted_at, datetime)

    # Restore
    entity.restore()
    assert entity.is_deleted is False
    assert entity.deleted_at is None


def test_domain_entity_event_registration() -> None:
    entity = SampleEntity(name="Acme")
    event = DomainEvent(event_type="entity.created", aggregate_id=entity.id)
    
    entity.register_event(event)
    events = entity.clear_events()
    assert len(events) == 1
    assert events[0] is event
    
    # Verify cleared
    assert len(entity.clear_events()) == 0


# ---------------------------------------------------------------------------
# 4. Domain Service Tests
# ---------------------------------------------------------------------------

class SampleDomainService(DomainService):
    def validate_name(self, name: str) -> None:
        self._check_invariant(len(name) > 3, "Name must be longer than 3 characters", "INVALID_NAME")


def test_domain_service_invariant_check() -> None:
    service = SampleDomainService()
    
    # Valid
    service.validate_name("Alice")
    
    # Invalid
    with pytest.raises(ValidationError) as exc_info:
        service.validate_name("Bob")
    assert exc_info.value.code == "INVALID_NAME"
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 5. Use Case Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_use_case_event_dispatching() -> None:
    publisher = FakeEventPublisher()
    use_case = UseCase(event_publisher=publisher)

    entity = SampleEntity(name="Acme")
    event = DomainEvent(event_type="test.event", aggregate_id=entity.id)
    entity.register_event(event)

    await use_case._publish_events(entity)
    assert len(publisher.published_events) == 1
    assert publisher.published_events[0] is event


@pytest.mark.asyncio
async def test_use_case_uow_tracking() -> None:
    uow = FakeUnitOfWork()
    use_case = UseCase(uow=uow)

    entity = SampleEntity(name="Acme")
    event = DomainEvent(event_type="test.event", aggregate_id=entity.id)
    entity.register_event(event)

    await use_case._publish_events(entity)
    # Unit of Work should intercept and track it, delaying direct publishing
    assert len(uow.tracked_entities) == 1
    assert uow.tracked_entities[0] is entity


# ---------------------------------------------------------------------------
# 6. Event Bus Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_bus_pub_sub() -> None:
    bus = EventBus()
    received_events = []

    async def sample_handler(event: DomainEvent) -> None:
        received_events.append(event)

    bus.subscribe("regulation.published", sample_handler)

    event = DomainEvent(event_type="regulation.published")
    # Using publish_and_wait so we synchronously resolve execution of handlers in the test
    await bus.publish_and_wait(event)

    assert len(received_events) == 1
    assert received_events[0] is event


@pytest.mark.asyncio
async def test_event_bus_wildcard_matching() -> None:
    bus = EventBus()
    received_events = []

    async def sample_handler(event: DomainEvent) -> None:
        received_events.append(event)

    bus.subscribe("regulation.*", sample_handler)

    event1 = DomainEvent(event_type="regulation.published")
    event2 = DomainEvent(event_type="regulation.deleted")
    event3 = DomainEvent(event_type="assessment.created")

    await bus.publish_and_wait(event1)
    await bus.publish_and_wait(event2)
    await bus.publish_and_wait(event3)

    assert len(received_events) == 2
    assert event1 in received_events
    assert event2 in received_events
    assert event3 not in received_events


@pytest.mark.asyncio
async def test_event_bus_handler_isolation() -> None:
    bus = EventBus()
    executed_fine = False

    async def bad_handler(event: DomainEvent) -> None:
        raise RuntimeError("Something failed!")

    async def good_handler(event: DomainEvent) -> None:
        nonlocal executed_fine
        executed_fine = True

    bus.subscribe("test.event", bad_handler)
    bus.subscribe("test.event", good_handler)

    event = DomainEvent(event_type="test.event")
    await bus.publish_and_wait(event)

    assert executed_fine is True
    assert len(bus.dead_letter_queue) == 1
    assert bus.dead_letter_queue[0][0] is event
    assert isinstance(bus.dead_letter_queue[0][1], RuntimeError)


# ---------------------------------------------------------------------------
# 7. Task Scheduler Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_once_execution() -> None:
    scheduler = TaskScheduler()
    executed = False

    async def sample_task() -> None:
        nonlocal executed
        executed = True

    scheduler.schedule_once("test_once", sample_task, delay_seconds=0.1)
    scheduler.start()
    
    # Wait for execution (scheduler loop runs once per second)
    await asyncio.sleep(1.2)
    await scheduler.shutdown()

    assert executed is True


# ---------------------------------------------------------------------------
# 8. InMemoryRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_in_memory_repository() -> None:
    repo = InMemoryRepository[SampleEntity]()
    entity = SampleEntity(name="Acme")

    await repo.save(entity)
    assert await repo.exists(entity.id) is True

    fetched = await repo.get_by_id(entity.id)
    assert fetched is entity

    # Search & Filter
    results, total = await repo.search(filters={"name": "Acme"})
    assert total == 1
    assert results[0] is entity

    results_none, total_none = await repo.search(filters={"name": "Nonexistent"})
    assert total_none == 0

    await repo.delete(entity.id)
    assert await repo.exists(entity.id) is False
