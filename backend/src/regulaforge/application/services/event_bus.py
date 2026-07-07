"""In-process event bus for decoupling application components."""

import asyncio
import fnmatch
import logging
from collections.abc import Awaitable, Callable
from typing import Optional

from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.config.logging import get_logger
from regulaforge.domain.events.base import DomainEvent

logger = get_logger(__name__)


class EventBus(EventPublisher):
    """In-process event bus for event dispatch and subscription matching.

    Supports wildcard subscriptions (e.g. ``"regulation.*"``), handler
    isolation, sync/async publishing, dead-letter collection, and basic
    metrics tracking.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[DomainEvent], Awaitable[None]]]] = {}
        self._dead_letter_queue: list[tuple[DomainEvent, Exception]] = []
        self._metrics = {
            "published": 0,
            "consumed": 0,
            "failed": 0,
        }

    def subscribe(
        self,
        event_pattern: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        """Subscribe a handler to events matching a pattern.

        Args:
            event_pattern: The event type pattern (e.g. ``"regulation.published"`` or ``"regulation.*"``).
            handler: An async callable that accepts a DomainEvent.
        """
        if event_pattern not in self._handlers:
            self._handlers[event_pattern] = []
        self._handlers[event_pattern].append(handler)
        logger.debug("Registered handler for event pattern: %s", event_pattern)

    def unsubscribe(
        self,
        event_pattern: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        """Unsubscribe a handler from a pattern."""
        if event_pattern in self._handlers:
            try:
                self._handlers[event_pattern].remove(handler)
            except ValueError:
                pass

    def _get_matching_handlers(
        self,
        event_type: str,
    ) -> list[Callable[[DomainEvent], Awaitable[None]]]:
        """Find all handlers that match the event type pattern using fnmatch."""
        matched = []
        for pattern, handlers in self._handlers.items():
            if fnmatch.fnmatchcase(event_type, pattern):
                matched.extend(handlers)
        return matched

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event asynchronously.

        Dispatches the event to matching handlers in the background.

        Args:
            event: The domain event to publish.
        """
        self._metrics["published"] += 1
        handlers = self._get_matching_handlers(event.event_type)
        if not handlers:
            logger.debug("No handlers registered for event type: %s", event.event_type)
            return

        # Fire and forget / run concurrently in background tasks
        for handler in handlers:
            asyncio.create_task(self._safe_execute_handler(handler, event))

    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """Publish a batch of events asynchronously."""
        for event in events:
            await self.publish(event)

    async def publish_delayed(self, event: DomainEvent, delay_seconds: int) -> None:
        """Publish an event after a delay."""
        async def _delayed():
            await asyncio.sleep(delay_seconds)
            await self.publish(event)

        asyncio.create_task(_delayed())

    async def publish_and_wait(self, event: DomainEvent) -> None:
        """Publish an event and wait for all handlers to complete.

        Args:
            event: The domain event to publish.
        """
        self._metrics["published"] += 1
        handlers = self._get_matching_handlers(event.event_type)
        if not handlers:
            logger.debug("No handlers registered for event type: %s", event.event_type)
            return

        tasks = [self._safe_execute_handler(handler, event) for handler in handlers]
        await asyncio.gather(*tasks)

    async def _safe_execute_handler(
        self,
        handler: Callable[[DomainEvent], Awaitable[None]],
        event: DomainEvent,
    ) -> None:
        """Execute a single handler safely, isolating errors and updating metrics."""
        try:
            await handler(event)
            self._metrics["consumed"] += 1
        except Exception as exc:
            self._metrics["failed"] += 1
            handler_name = getattr(handler, "__name__", str(handler))
            logger.error(
                "Error executing handler %s for event %s: %s",
                handler_name,
                event.event_id,
                exc,
                exc_info=True,
            )
            self._dead_letter_queue.append((event, exc))

    @property
    def metrics(self) -> dict[str, int]:
        """Retrieve execution metrics."""
        return dict(self._metrics)

    @property
    def dead_letter_queue(self) -> list[tuple[DomainEvent, Exception]]:
        """Retrieve dead-lettered events."""
        return list(self._dead_letter_queue)

    def clear_dead_letters(self) -> None:
        """Clear the dead-letter queue."""
        self._dead_letter_queue.clear()
