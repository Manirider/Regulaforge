"""Event publisher adapter implementations.

Provides logging and RabbitMQ-based event publishing adapters
for the EventPublisher port interface.
"""

import json

from regulaforge.application.ports.event_publisher import (
    EventPublisher,
    EventPublishError,
)
from regulaforge.config.logging import get_logger
from regulaforge.domain.events.base import DomainEvent

logger = get_logger(__name__)


class LoggingEventPublisher(EventPublisher):
    """Logging-based event publisher.

    Used in development/testing. Logs events at INFO level.
    In production, replace with RabbitMQEventPublisher.
    """

    async def publish(self, event: DomainEvent) -> None:
        """Log the event to the console."""
        logger.info(
            "EVENT: %s | aggregate=%s:%s | id=%s",
            event.event_type,
            event.aggregate_type,
            event.aggregate_id,
            event.event_id,
        )

    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """Log multiple events."""
        for event in events:
            await self.publish(event)

    async def publish_delayed(self, event: DomainEvent, delay_seconds: int) -> None:
        """Log delayed event."""
        logger.info(
            "EVENT (delayed %ds): %s | aggregate=%s:%s",
            delay_seconds,
            event.event_type,
            event.aggregate_type,
            event.aggregate_id,
        )


class RabbitMQEventPublisher(EventPublisher):
    """RabbitMQ-based event publisher for production use.

    NOTE: Requires aio-pika library and RabbitMQ server.
    """

    def __init__(self) -> None:
        self._connection = None
        self._channel = None
        self._exchange = None
        self._initialized = False
        self._exchange_name = "regulaforge"

    async def _ensure_connected(self) -> None:
        """Lazy-initialize RabbitMQ connection."""
        if not self._initialized:
            try:
                import aio_pika

                from regulaforge.config.settings import settings

                self._connection = await aio_pika.connect_robust(
                    str(settings.broker.url)
                )
                self._channel = await self._connection.channel()
                self._exchange = await self._channel.declare_exchange(
                    name=self._exchange_name,
                    type=aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                self._initialized = True
                logger.info("RabbitMQ publisher connected: exchange=%s", self._exchange_name)
            except Exception as e:
                logger.error("Failed to connect to RabbitMQ: %s", e)
                raise EventPublishError(f"Failed to connect to RabbitMQ: {e}")

    async def publish(self, event: DomainEvent) -> None:
        """Publish event to RabbitMQ exchange."""
        if not self._initialized:
            logger.warning("RabbitMQ not connected, falling back to log")
            publisher = LoggingEventPublisher()
            await publisher.publish(event)
            return

        try:
            import aio_pika

            message_body = json.dumps(event.to_dict(), default=str).encode()
            message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={
                    "event_type": event.event_type,
                    "event_id": str(event.event_id),
                    "correlation_id": event.correlation_id,
                },
            )
            await self._exchange.publish(
                message,
                routing_key=event.event_type,
            )
            logger.debug("Published event: %s", event.event_type)
        except Exception as e:
            logger.error("Failed to publish event %s: %s", event.event_type, e)
            raise EventPublishError(f"Failed to publish event: {e}")

    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(event)

    async def publish_delayed(self, event: DomainEvent, delay_seconds: int) -> None:
        """Publish event with delayed delivery."""
        if not self._initialized:
            publisher = LoggingEventPublisher()
            await publisher.publish_delayed(event, delay_seconds)
            return

        try:
            import aio_pika

            # Create a delayed message exchange (requires rabbitmq_delayed_message_exchange plugin)
            message_body = json.dumps(event.to_dict(), default=str).encode()
            message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers={"x-delay": delay_seconds * 1000},
            )
            await self._exchange.publish(
                message,
                routing_key=event.event_type,
            )
            logger.debug("Published delayed event: %s (delay=%ds)", event.event_type, delay_seconds)
        except Exception as e:
            logger.error("Failed to publish delayed event: %s", e)
            raise EventPublishError(f"Failed to publish delayed event: {e}")

    async def close(self) -> None:
        """Close the RabbitMQ connection."""
        if self._connection:
            await self._connection.close()
            self._initialized = False
            logger.info("RabbitMQ connection closed")
