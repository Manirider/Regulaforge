"""Base use case with common infrastructure."""

import logging
from typing import Any, Optional

from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.unit_of_work import UnitOfWork
from regulaforge.common.exceptions import ConfigurationError
from regulaforge.config.logging import get_logger


class UseCase:
    """Abstract base for all use cases.

    Provides logging, event publishing, unit of work coordination,
    and error handling to every use case implementation.
    """

    def __init__(
        self,
        event_publisher: Optional[EventPublisher] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> None:
        self._logger = get_logger(self.__class__.__name__)
        self._event_publisher = event_publisher
        self._uow = uow

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @property
    def uow(self) -> Optional[UnitOfWork]:
        """Access the configured Unit of Work."""
        return self._uow

    def _require_uow(self) -> UnitOfWork:
        """Assert that a Unit of Work is configured, returning it if present.

        Raises:
            ConfigurationError: If no Unit of Work is configured.
        """
        if self._uow is None:
            raise ConfigurationError(
                f"Unit of Work is required for use case {self.__class__.__name__} "
                f"but was not configured."
            )
        return self._uow

    async def _publish_events(self, entity: Any) -> None:
        """Publish domain events registered on an entity."""
        # If we have a Unit of Work, register the entity for transaction-scoped dispatch
        if self._uow is not None and hasattr(self._uow, "track"):
            self._uow.track(entity)
            return

        if self._event_publisher:
            events = entity.clear_events()
            if events:
                await self._event_publisher.publish_batch(events)
                self._logger.debug(
                    "Published %d domain events for %s %s",
                    len(events),
                    entity.__class__.__name__,
                    entity.id,
                )

    async def _publish_event(self, event: Any) -> None:
        """Publish a single domain event."""
        if self._event_publisher:
            await self._event_publisher.publish(event)
            self._logger.debug("Published event %s", event.event_type)
