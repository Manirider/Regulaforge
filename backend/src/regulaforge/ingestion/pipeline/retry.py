"""
Configurable async retry with exponential backoff and jitter.

Provides two retry primitives:

* ``retry_with_backoff`` — for regular async functions.
* ``retry_generator_with_backoff`` — for async generators.

Both support configurable retry counts, exponential backoff with full jitter,
and selective exception filtering.  Cancellation-safe (:func:`asyncio.shield`
is used around each attempt).
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import AsyncGenerator, Awaitable, Callable, TypeVar

from regulaforge.common.exceptions import RetryExhaustedError

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0
DEFAULT_JITTER_FACTOR = 0.1
DEFAULT_MULTIPLIER = 2.0


@dataclass
class RetryConfig:
    """Retry policy for transient failures.

    Attributes:
        max_retries: Maximum number of attempts (including the first).
        base_delay: Initial delay in seconds before the first retry.
        max_delay: Cap on the delay in seconds (prevents unbounded backoff).
        jitter_factor: Fraction of the current delay to use as jitter range.
        multiplier: Exponential factor applied after each retry.
        retryable_exceptions: Tuple of exception types that trigger a retry.
    """

    max_retries: int = DEFAULT_MAX_RETRIES
    base_delay: float = DEFAULT_BASE_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    jitter_factor: float = DEFAULT_JITTER_FACTOR
    multiplier: float = DEFAULT_MULTIPLIER
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


def calculate_backoff(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    multiplier: float = DEFAULT_MULTIPLIER,
    jitter_factor: float = DEFAULT_JITTER_FACTOR,
) -> float:
    """Calculate the sleep delay for a given retry attempt.

    Uses truncated exponential backoff with symmetric jitter:

        delay = min(base * multiplier^(attempt-1), max_delay)
        jitter = uniform(-jitter_factor * delay, +jitter_factor * delay)
        result = max(0.0, delay + jitter)

    Args:
        attempt: 1-based retry attempt number.
        base_delay: Base delay in seconds.
        max_delay: Maximum delay cap in seconds.
        multiplier: Exponential backoff multiplier.
        jitter_factor: Fraction of delay to use as maximum jitter offset.

    Returns:
        Non-negative delay in seconds.
    """
    delay = min(base_delay * (multiplier ** (attempt - 1)), max_delay)
    jitter = random.uniform(-jitter_factor * delay, jitter_factor * delay)
    return max(0.0, delay + jitter)


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    *args: object,
    retry_config: RetryConfig | None = None,
    **kwargs: object,
) -> T:
    """Execute an async callable with retry-and-backoff semantics.

    The callable is invoked inside :func:`asyncio.shield` so that
    cancellation does not leave side-effects in an inconsistent state.

    Args:
        func: Async callable to invoke.
        retry_config: Retry policy (uses defaults if omitted).
        args, kwargs: Forwarded to *func*.

    Returns:
        The return value of *func* on success.

    Raises:
        RetryExhaustedError: After all configured attempts are exhausted.
        Non-retryable exceptions are re-raised immediately.
    """
    config = retry_config or RetryConfig()
    last_exception: Exception | None = None
    for attempt in range(1, config.max_retries + 1):
        try:
            return await asyncio.shield(func(*args, **kwargs))
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt < config.max_retries:
                delay = calculate_backoff(
                    attempt=attempt,
                    base_delay=config.base_delay,
                    max_delay=config.max_delay,
                    multiplier=config.multiplier,
                    jitter_factor=config.jitter_factor,
                )
                await asyncio.sleep(delay)
    raise RetryExhaustedError(
        f"Failed after {config.max_retries} attempts",
        details={
            "max_retries": config.max_retries,
            "last_error": str(last_exception),
        },
    ) from last_exception


async def retry_generator_with_backoff(
    gen_func: Callable[..., AsyncGenerator[T, None]],
    *args: object,
    retry_config: RetryConfig | None = None,
    **kwargs: object,
) -> AsyncGenerator[T, None]:
    """Wrap an async generator with retry-and-backoff semantics.

    If the generator raises a retryable exception part-way through, the
    entire generator is re-started from scratch on the next attempt.

    Args:
        gen_func: Async-generator factory to invoke.
        retry_config: Retry policy (uses defaults if omitted).
        args, kwargs: Forwarded to *gen_func*.

    Yields:
        Items produced by *gen_func*.

    Raises:
        RetryExhaustedError: After all configured attempts are exhausted.
    """
    config = retry_config or RetryConfig()
    last_exception: Exception | None = None
    for attempt in range(1, config.max_retries + 1):
        try:
            async for item in gen_func(*args, **kwargs):
                yield item
            return
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt < config.max_retries:
                delay = calculate_backoff(
                    attempt=attempt,
                    base_delay=config.base_delay,
                    max_delay=config.max_delay,
                    multiplier=config.multiplier,
                    jitter_factor=config.jitter_factor,
                )
                await asyncio.sleep(delay)
    raise RetryExhaustedError(
        f"Generator failed after {config.max_retries} attempts",
        details={
            "max_retries": config.max_retries,
            "last_error": str(last_exception),
        },
    ) from last_exception
