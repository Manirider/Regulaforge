"""Event publisher port interface.

Defines the contract for publishing domain events to the
message bus, enabling event-driven communication between
bounded contexts.
"""

from abc import ABC, abstractmethod

from regulaforge.domain.events.base import DomainEvent


class EventPublisher(ABC):
    """Port interface for publishing domain events.

    Implementations can use RabbitMQ, Kafka, SQS, or any
    other message broker technology.
    """

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event.

        Args:
            event: The domain event to publish.

        Raises:
            EventPublishError: If event publishing fails.
        """
        ...

    @abstractmethod
    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """Publish multiple domain events atomically.

        Args:
            events: List of domain events to publish.

        Raises:
            EventPublishError: If batch publishing fails.
        """
        ...

    @abstractmethod
    async def publish_delayed(self, event: DomainEvent, delay_seconds: int) -> None:
        """Publish an event with a delivery delay.

        Args:
            event: The domain event to publish.
            delay_seconds: Delay before the event is delivered.

        Raises:
            EventPublishError: If event publishing fails.
        """
        ...


from regulaforge.common.exceptions import EventPublishError  # noqa: F401 - re-exported for backward compatibility
