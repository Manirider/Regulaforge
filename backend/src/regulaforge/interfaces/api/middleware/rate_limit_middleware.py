from __future__ import annotations

import time
from collections.abc import Callable
from typing import Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


class InMemoryTokenBucket:
    def __init__(self, capacity: int, refill_rate: float, refill_interval: float = 1.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_interval = refill_interval
        self.tokens: float = float(capacity)
        self.last_refill: float = time.monotonic()

    def consume(self, cost: int = 1) -> tuple[bool, float, float]:
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_count = int(elapsed / self.refill_interval)
        if refill_count > 0:
            self.tokens = min(self.capacity, self.tokens + refill_count * self.refill_rate)
            self.last_refill += refill_count * self.refill_interval
        if self.tokens >= cost:
            self.tokens -= cost
            return True, self.tokens, 0.0
        retry_after = (cost - self.tokens) / self.refill_rate * self.refill_interval
        return False, self.tokens, retry_after


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        default_capacity: int = 60,
        default_refill_rate: float = 1.0,
        refill_interval: float = 1.0,
        excluded_paths: Optional[list[str]] = None,
    ) -> None:
        super().__init__(app)
        self._default_capacity = default_capacity
        self._default_refill_rate = default_refill_rate
        self._refill_interval = refill_interval
        self._excluded_paths = set(excluded_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"])
        self._buckets: dict[str, InMemoryTokenBucket] = {}

    def _get_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        return f"{client_ip}:{request.url.path}"

    def _should_rate_limit(self, request: Request) -> bool:
        path = request.url.path.lower()
        return all(not path.startswith(excluded.lower()) for excluded in self._excluded_paths)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self._should_rate_limit(request):
            return await call_next(request)

        key = self._get_key(request)
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = InMemoryTokenBucket(self._default_capacity, self._default_refill_rate, self._refill_interval)
            self._buckets[key] = bucket

        allowed, remaining, retry_after = bucket.consume()

        if not allowed:
            logger.warning("Rate limit exceeded for %s", key)
            return Response(
                status_code=429,
                content='{"error":{"code":"RATE_LIMITED","message":"Too many requests. Please try again later."}}',
                media_type="application/json",
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(self._default_capacity),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._default_capacity)
        response.headers["X-RateLimit-Remaining"] = str(max(0, int(remaining)))
        return response


def add_rate_limit_middleware(
    app: FastAPI,
    capacity: int = settings.security.rate_limit_per_minute,
    refill_rate: float = 1.0,
    excluded_paths: Optional[list[str]] = None,
) -> None:
    app.add_middleware(
        RateLimitMiddleware,
        default_capacity=capacity,
        default_refill_rate=refill_rate,
        excluded_paths=excluded_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"],
    )
    logger.info("Rate limit middleware registered (capacity=%d/min)", capacity)
