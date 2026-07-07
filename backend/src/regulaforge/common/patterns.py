"""Design pattern implementations: registry, observable, circuit breaker."""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum, auto
from typing import Any, Callable, Generic, Optional, TypeVar

from regulaforge.common.exceptions import (
    CircuitBreakerOpenError,
    ExternalServiceError,
    RetryExhaustedError,
)


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
logger = logging.getLogger(__name__)


# ─── Registry Pattern ────────────────────────────────────────────────────

class Registry(Generic[K, V]):
    """A type-safe registry mapping keys to values.

    Usage::

        strategies = Registry[str, BaseStrategy]()
        strategies.register("quick", QuickStrategy)
        strategy = strategies.get("quick")
    """

    def __init__(self) -> None:
        self._entries: dict[K, type[V] | V] = {}

    def register(self, key: K, value: type[V] | V) -> None:
        if key in self._entries:
            logger.warning("Registry key %r overwritten", key)
        self._entries[key] = value

    def unregister(self, key: K) -> None:
        self._entries.pop(key, None)

    def get(self, key: K) -> type[V] | V:
        if key not in self._entries:
            raise KeyError(f"Registry key {key!r} not found")
        return self._entries[key]

    def has(self, key: K) -> bool:
        return key in self._entries

    def keys(self) -> list[K]:
        return list(self._entries)

    def __contains__(self, key: K) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"Registry({list(self._entries.keys())})"


# ─── Observer Pattern ────────────────────────────────────────────────────

EventHandler = Callable[..., Any]


class Observable:
    """Simple observable implementation for event-driven communication.

    Usage::

        hub = Observable()
        hub.on("user.created", send_welcome_email)
        await hub.emit("user.created", user_id=42)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def on(self, event: str, handler: EventHandler) -> None:
        """Register a handler for *event*."""
        self._handlers.setdefault(event, []).append(handler)

    def off(self, event: str, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        handlers = self._handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Emit *event*, calling all registered handlers.

        Returns a list of results from each handler.
        """
        results: list[Any] = []
        for handler in list(self._handlers.get(event, [])):
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                results.append(result)
            except Exception:
                logger.exception("Handler %r failed for event %r", handler, event)
        return results

    def clear(self, event: Optional[str] = None) -> None:
        """Remove all handlers for *event*, or all if *event* is None."""
        if event:
            self._handlers.pop(event, None)
        else:
            self._handlers.clear()

    def handler_count(self, event: Optional[str] = None) -> int:
        if event:
            return len(self._handlers.get(event, []))
        return sum(len(h) for h in self._handlers.values())

    def __repr__(self) -> str:
        return f"Observable(events={list(self._handlers.keys())})"


# ─── Circuit Breaker Pattern ─────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreaker(Generic[T]):
    """Circuit breaker for protecting external service calls.

    Usage::

        cb = CircuitBreaker("openai", failure_threshold=5, recovery_timeout=30.0)

        async with cb:
            result = await call_openai(prompt)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    async def _try_half_open(self) -> bool:
        """Transition to HALF_OPEN if recovery timeout has elapsed."""
        if self._state != CircuitState.OPEN:
            return self._state == CircuitState.HALF_OPEN
        if self._last_failure_time is None:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self.recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
            logger.info("Circuit %r transitioned to HALF_OPEN", self.name)
            return True
        return False

    async def __aenter__(self) -> CircuitBreaker[T]:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit {self.name!r} is half-open and at capacity",
                        details={"circuit": self.name},
                    )
                self._half_open_calls += 1
                return self

            if self._state == CircuitState.OPEN:
                if await self._try_half_open():
                    self._half_open_calls += 1
                    return self
                raise CircuitBreakerOpenError(
                    f"Circuit {self.name!r} is open",
                    retry_after=self.recovery_timeout,
                    details={"circuit": self.name},
                )
            return self

    async def __aexit__(
        self,
        exc_type: type,
        exc_val: Exception,
        exc_tb: object,
    ) -> None:
        async with self._lock:
            if exc_type is None:
                self._on_success()
            elif self._is_failure(exc_type):
                self._on_failure()

    def _on_success(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info("Circuit %r closed after successful call", self.name)

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit %r opened (failures: %d/%d)",
                self.name, self._failure_count, self.failure_threshold,
            )

    @staticmethod
    def _is_failure(exc_type: type) -> bool:
        return issubclass(exc_type, (ExternalServiceError, RetryExhaustedError, TimeoutError))

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info("Circuit %r manually reset", self.name)

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.name}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


__all__ = [
    "Registry",
    "Observable",
    "CircuitBreaker",
    "CircuitState",
]
