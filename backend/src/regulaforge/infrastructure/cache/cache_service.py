from __future__ import annotations

import json
import time
from collections.abc import Callable, Coroutine
from typing import Any, Optional, TypeVar

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)

T = TypeVar("T")


class CacheService:
    def __init__(self) -> None:
        self._redis = None
        self._enabled = True
        self._local: dict[str, tuple[Any, float]] = {}
        self._default_ttl = settings.cache.default_ttl
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                str(settings.cache.url),
                max_connections=settings.cache.max_connections,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            logger.info("CacheService initialized: %s", settings.cache.url)
        except Exception as e:
            logger.warning("Redis unavailable, using in-memory cache: %s", e)
            self._enabled = False

    def _make_key(self, key: str) -> str:
        return f"cache:{key}"

    async def get(self, key: str) -> Optional[Any]:
        redis_key = self._make_key(key)
        if self._redis is not None:
            try:
                cached = await self._redis.get(redis_key)
                if cached is not None:
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Cache read error: %s", e)
        entry = self._local.get(redis_key)
        if entry is not None:
            value, expiry = entry
            if expiry == 0 or time.monotonic() < expiry:
                return value
            del self._local[redis_key]
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        redis_key = self._make_key(key)
        effective_ttl = ttl if ttl is not None else self._default_ttl
        if self._redis is not None:
            try:
                serialized = json.dumps(value, default=str)
                await self._redis.setex(redis_key, effective_ttl, serialized)
                return
            except Exception as e:
                logger.warning("Cache write error: %s", e)
        expiry = time.monotonic() + effective_ttl if effective_ttl > 0 else 0
        self._local[redis_key] = (value, expiry)

    async def get_or_compute(
        self,
        key: str,
        compute_func: Callable[[], Coroutine[Any, Any, T]],
        ttl: Optional[int] = None,
    ) -> T:
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await compute_func()
        await self.set(key, value, ttl)
        return value

    async def delete(self, key: str) -> None:
        redis_key = self._make_key(key)
        self._local.pop(redis_key, None)
        if self._redis is not None:
            try:
                await self._redis.delete(redis_key)
            except Exception as e:
                logger.warning("Cache delete error: %s", e)

    async def clear_pattern(self, pattern: str) -> None:
        redis_key_pattern = self._make_key(pattern)
        self._local.clear()
        if self._redis is not None:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(cursor=cursor, match=redis_key_pattern, count=100)
                    if keys:
                        await self._redis.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning("Cache clear error: %s", e)

    async def health_check(self) -> bool:
        if self._redis is not None:
            try:
                await self._redis.ping()
                return True
            except Exception:
                return False
        return True
