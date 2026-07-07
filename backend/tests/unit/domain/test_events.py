"""Unit tests for domain events."""

from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class TestDomainEvent:
    def test_create(self):
        event = DomainEvent(
            event_type="regulation.created",
            aggregate_id="some-id",
            data={"key": "value"},
        )
        assert event.event_type == "regulation.created"
        assert event.data == {"key": "value"}
        assert event.event_id is not None
        assert isinstance(event.event_id, UUID)

    def test_default_timestamp(self):
        event = DomainEvent()
        assert event.timestamp is not None

    def test_default_values(self):
        event = DomainEvent()
        assert event.event_type == ""
        assert event.aggregate_id is None
        assert event.data == {}
