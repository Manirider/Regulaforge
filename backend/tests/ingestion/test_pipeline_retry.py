from __future__ import annotations

import asyncio
import sys
from typing import AsyncGenerator

if sys.version_info >= (3, 11):
    from asyncio import timeout
else:
    from async_timeout import timeout

import pytest
from regulaforge.common.exceptions import RetryExhaustedError
from regulaforge.ingestion.pipeline.retry import (
    RetryConfig,
    calculate_backoff,
    retry_generator_with_backoff,
    retry_with_backoff,
)


class TestCalculateBackoff:
    def test_first_attempt_base_delay(self) -> None:
        delay = calculate_backoff(attempt=1, base_delay=1.0, jitter_factor=0.0)
        assert delay == 1.0

    def test_exponential_increase(self) -> None:
        d1 = calculate_backoff(attempt=1, base_delay=1.0, multiplier=2.0, jitter_factor=0.0)
        d2 = calculate_backoff(attempt=2, base_delay=1.0, multiplier=2.0, jitter_factor=0.0)
        d3 = calculate_backoff(attempt=3, base_delay=1.0, multiplier=2.0, jitter_factor=0.0)
        assert d1 == 1.0
        assert d2 == 2.0
        assert d3 == 4.0

    def test_capped_at_max_delay(self) -> None:
        delay = calculate_backoff(attempt=10, base_delay=1.0, max_delay=60.0, multiplier=2.0, jitter_factor=0.0)
        assert delay == 60.0

    def test_jitter_in_range(self) -> None:
        delays = [
            calculate_backoff(attempt=2, base_delay=1.0, jitter_factor=0.5)
            for _ in range(100)
        ]
        for d in delays:
            assert 1.0 <= d <= 3.0

    def test_non_negative(self) -> None:
        delay = calculate_backoff(attempt=1, base_delay=0.1, jitter_factor=2.0)
        assert delay >= 0.0


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self) -> None:
        call_count = 0

        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await retry_with_backoff(succeed)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_succeed(self) -> None:
        call_count = 0

        async def fail_twice() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "ok"

        result = await retry_with_backoff(
            fail_twice,
            retry_config=RetryConfig(max_retries=5, base_delay=0.01, jitter_factor=0.0),
        )
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhaust_retries(self) -> None:
        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("persistent error")

        with pytest.raises(RetryExhaustedError) as excinfo:
            await retry_with_backoff(
                always_fail,
                retry_config=RetryConfig(max_retries=3, base_delay=0.01, jitter_factor=0.0),
            )
        assert call_count == 3
        assert "3 attempts" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self) -> None:
        async def fail() -> str:
            raise TypeError("non-retryable")

        with pytest.raises(TypeError):
            await retry_with_backoff(
                fail,
                retry_config=RetryConfig(retryable_exceptions=(ValueError,)),
            )

    @pytest.mark.asyncio
    async def test_custom_retry_config(self) -> None:
        call_count = 0

        async def fail() -> str:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("custom")

        with pytest.raises(RetryExhaustedError):
            await retry_with_backoff(
                fail,
                retry_config=RetryConfig(max_retries=2, base_delay=0.01, retryable_exceptions=(RuntimeError,)),
            )
        assert call_count == 2


class TestRetryGeneratorWithBackoff:
    @pytest.mark.asyncio
    async def test_successful_generator(self) -> None:
        async def gen() -> AsyncGenerator[int, None]:
            for i in range(3):
                yield i

        items = []
        async with timeout(5):
            async for item in retry_generator_with_backoff(gen):
                items.append(item)
        assert items == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_retry_generator_then_succeed(self) -> None:
        call_count = 0

        async def gen() -> AsyncGenerator[int, None]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("network error")
            yield 42

        items = []
        async with timeout(5):
            async for item in retry_generator_with_backoff(
                gen,
                retry_config=RetryConfig(max_retries=5, base_delay=0.01, jitter_factor=0.0),
            ):
                items.append(item)
        assert items == [42]
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_generator_exhaust_retries(self) -> None:
        async def gen() -> AsyncGenerator[int, None]:
            raise OSError("persistent")
            yield  # pragma: no cover

        with pytest.raises(RetryExhaustedError):
            async with timeout(5):
                async for _ in retry_generator_with_backoff(
                    gen,
                    retry_config=RetryConfig(max_retries=2, base_delay=0.01, jitter_factor=0.0),
                ):
                    pass  # pragma: no cover
