"""General-purpose utilities used across the application."""

from __future__ import annotations

import asyncio
import functools
import random
import re
import threading
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Optional, ParamSpec, TypeVar, overload

from regulaforge.common.types import LoggerProtocol


P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# ─── Timing ──────────────────────────────────────────────────────────────

@overload
def timed(
    func: None = None,
    *,
    logger: Optional[LoggerProtocol] = None,
    level: str = "info",
    message: str = "Completed in {duration:.3f}s",
) -> _TimedContext:
    ...


@overload
def timed(
    func: F,
    *,
    logger: Optional[LoggerProtocol] = None,
    level: str = "info",
    message: str = "Completed in {duration:.3f}s",
) -> F:
    ...


def timed(
    func: Optional[F] = None,
    *,
    logger: Optional[LoggerProtocol] = None,
    level: str = "info",
    message: str = "Completed in {duration:.3f}s",
) -> Any:
    """Decorator / context manager for timing execution.

    Usage as decorator::

        @timed(logger=my_logger)
        async def my_function():
            ...

    Usage as context manager::

        with timed():
            ...
    """
    if func is not None:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.monotonic() - start
                _log(logger, level, message.format(duration=duration))

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.monotonic() - start
                _log(logger, level, message.format(duration=duration))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return _TimedContext(logger=logger, level=level, message=message)


class _TimedContext:
    """Context manager for timing code blocks."""

    def __init__(
        self,
        logger: Optional[LoggerProtocol] = None,
        level: str = "info",
        message: str = "Completed in {duration:.3f}s",
    ) -> None:
        self._logger = logger
        self._level = level
        self._message = message

    def __enter__(self) -> _TimedContext:
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: Any) -> None:
        duration = time.monotonic() - self._start
        _log(self._logger, self._level, self._message.format(duration=duration))


def _log(logger: Optional[LoggerProtocol], level: str, msg: str) -> None:
    if logger is None:
        return
    getattr(logger, level, logger.info)(msg)


# ─── Async retry ─────────────────────────────────────────────────────────

def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    logger: Optional[LoggerProtocol] = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for async functions with exponential backoff retry.

    Usage::

        @retry(max_attempts=3, logger=logger)
        async def fetch_data(url: str) -> dict:
            ...
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        raise
                    delay = min(
                        base_delay * (backoff_factor ** (attempt - 1)),
                        max_delay,
                    )
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    if logger:
                        logger.warning(
                            "Attempt %d/%d failed: %s. Retrying in %.2fs...",
                            attempt, max_attempts, e, delay,
                        )
                    await asyncio.sleep(delay)
            raise RuntimeError("Retry loop fell through") from last_exception
        return wrapper
    return decorator


# ─── Singleton via metaclass ─────────────────────────────────────────────

class _SingletonMeta(type):
    """Thread-safe metaclass for the singleton pattern."""

    _instances: dict[type, Any] = {}
    _locks: dict[type, threading.Lock] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            lock = cls._locks.setdefault(cls, threading.Lock())
            with lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def singleton(cls: type[T]) -> type[T]:
    """Thread-safe class decorator enforcing singleton pattern via metaclass.

    Usage::

        @singleton
        class DatabasePool:
            ...
    """
    return _SingletonMeta(cls.__name__, cls.__bases__, dict(cls.__dict__))


# ─── Ensure awaitable ───────────────────────────────────────────────────

async def ensure_awaitable(value: T | Awaitable[T]) -> T:
    """Return the value directly if not awaitable; otherwise await.

    Useful for functions that may return either a coroutine or a plain value.
    """
    if asyncio.iscoroutine(value) or isinstance(value, Awaitable):
        return await value  # type: ignore[return-value]
    return value  # type: ignore[return-value]


# ─── String utilities ────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug.

    "Hello World! 123" -> "hello-world-123"
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def truncate(text: str, max_length: int = 120, suffix: str = "...") -> str:
    """Truncate text to a maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def format_datetime_iso(dt: Optional[datetime] = None) -> str:
    """Format a datetime as ISO 8601 string in UTC.

    Defaults to current UTC time if no datetime provided.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ─── Async utilities ─────────────────────────────────────────────────────

async def gather_with_concurrency(
    n: int,
    *tasks: Awaitable[T],
) -> list[T]:
    """Run awaitables with a concurrency limit.

    Like ``asyncio.gather`` but at most *n* tasks run simultaneously.
    """
    semaphore = asyncio.Semaphore(n)

    async def _wrapped(task: Awaitable[T]) -> T:
        async with semaphore:
            return await task

    return await asyncio.gather(*[_wrapped(t) for t in tasks])


def exponential_backoff(
    attempt: int,
    base: float = 1.0,
    cap: float = 60.0,
) -> float:
    """Compute exponential backoff delay with full jitter.

    ``delay = min(base * 2^attempt, cap) * random.uniform(0, 1)``
    """
    delay = min(base * (2 ** attempt), cap)
    return delay * random.uniform(0, 1)


# ─── Environment helpers ─────────────────────────────────────────────────

def str_to_bool(value: str | bool) -> bool:
    """Convert a string or boolean to a boolean.

    ``"true"``, ``"1"``, ``"yes"``, ``"y"`` (case-insensitive) → ``True``.
    All others → ``False``.
    """
    if isinstance(value, bool):
        return value
    return value.lower().strip() in {"true", "1", "yes", "y"}


def create_response(
    data: Optional[Any] = None,
    message: str = "Success",
    status: str = "ok",
) -> dict[str, Any]:
    """Standard API response envelope."""
    return {
        "status": status,
        "message": message,
        "data": data,
    }


__all__ = [
    "timed",
    "retry",
    "singleton",
    "ensure_awaitable",
    "slugify",
    "truncate",
    "format_datetime_iso",
    "gather_with_concurrency",
    "exponential_backoff",
    "str_to_bool",
    "create_response",
]
