"""Dashboard caching infrastructure.

Provides a Redis-backed caching layer for dashboard data with
configurable TTLs, tenant-scoped invalidation, and a
get-or-compute pattern for efficient data retrieval.
"""

import json
from collections.abc import Callable, Coroutine
from typing import Any, Optional, TypeVar

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)

T = TypeVar("T")


class DashboardCache:
    """Dashboard data cache with Redis backend.

    Provides tenant-scoped caching for dashboard metrics, charts,
    and snapshots. Falls back to compute-on-demand if Redis is
    unavailable.

    Cache key pattern: "dashboard:{tenant_id}:{metric_name}"
    """

    def __init__(self) -> None:
        """Initialize the DashboardCache.

        Attempts to establish a Redis connection using application
        settings. Gracefully handles Redis unavailability by logging
        a warning and operating in cache-miss mode.
        """
        self._redis = None
        self._enabled = True
        self._default_ttl = settings.cache.default_ttl
        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis connection pool.

        Attempts to connect to Redis. If the connection fails,
        caching is disabled and a warning is logged.
        """
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
            logger.info(
                "Dashboard cache initialized: %s (pool=%d)",
                settings.cache.url,
                settings.cache.max_connections,
            )
        except Exception as e:
            logger.warning(
                "Redis cache unavailable, operating in cache-miss mode: %s",
                e,
            )
            self._enabled = False
            self._redis = None

    def _make_key(self, cache_key: str) -> str:
        """Build a namespaced Redis key.

        Args:
            cache_key: The logical cache key.

        Returns:
            Full Redis key string.
        """
        return f"dashboard:{cache_key}"

    async def get_cached_or_compute(
        self,
        cache_key: str,
        compute_func: Callable[[], Coroutine[Any, Any, T]],
        ttl: Optional[int] = None,
    ) -> T:
        """Retrieve from cache or compute and cache.

        If the value exists in cache, returns it directly.
        Otherwise, calls compute_func, caches the result, and
        returns it.

        Args:
            cache_key: The cache key to look up.
            compute_func: Async function that computes the value.
            ttl: Time-to-live in seconds. Defaults to the
                application-level default TTL.

        Returns:
            The cached or computed value.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        redis_key = self._make_key(cache_key)

        if self._enabled and self._redis:
            try:
                cached = await self._redis.get(redis_key)
                if cached is not None:
                    logger.debug("Cache hit: %s", cache_key)
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Cache read error for %s: %s", cache_key, e)

        logger.debug("Cache miss: %s (computing)", cache_key)
        value = await compute_func()

        if self._enabled and self._redis:
            try:
                serialized = json.dumps(value, default=str)
                await self._redis.setex(redis_key, effective_ttl, serialized)
                logger.debug("Cached: %s (TTL=%ds)", cache_key, effective_ttl)
            except Exception as e:
                logger.warning("Cache write error for %s: %s", cache_key, e)

        return value

    async def get(self, cache_key: str) -> Optional[Any]:
        """Get a value from cache without computing.

        Args:
            cache_key: The cache key to look up.

        Returns:
            Cached value if found, None otherwise.
        """
        redis_key = self._make_key(cache_key)
        if not self._enabled or not self._redis:
            return None

        try:
            cached = await self._redis.get(redis_key)
            if cached is not None:
                logger.debug("Cache hit: %s", cache_key)
                return json.loads(cached)
        except Exception as e:
            logger.warning("Cache read error for %s: %s", cache_key, e)

        return None

    async def set(
        self,
        cache_key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set a value in cache.

        Args:
            cache_key: The cache key to set.
            value: The value to cache.
            ttl: Time-to-live in seconds.
        """
        if not self._enabled or not self._redis:
            return

        effective_ttl = ttl if ttl is not None else self._default_ttl
        redis_key = self._make_key(cache_key)

        try:
            serialized = json.dumps(value, default=str)
            await self._redis.setex(redis_key, effective_ttl, serialized)
            logger.debug("Cached: %s (TTL=%ds)", cache_key, effective_ttl)
        except Exception as e:
            logger.warning("Cache write error for %s: %s", cache_key, e)

    async def invalidate(self, tenant_id: str) -> None:
        """Invalidate all cached dashboard data for a tenant.

        Removes all cache entries matching the tenant's key prefix.

        Args:
            tenant_id: The tenant identifier.
        """
        if not self._enabled or not self._redis:
            return

        pattern = self._make_key(f"{tenant_id}:*")
        try:
            cursor = 0
            deleted_count = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break

            if deleted_count > 0:
                logger.info(
                    "Invalidated %d cache entries for tenant %s",
                    deleted_count, tenant_id,
                )

            global_cache_key = self._make_key(f"compliance_overview:{tenant_id}")
            await self._redis.delete(global_cache_key)
            logger.debug(
                "Cleared compliance_overview cache for tenant %s",
                tenant_id,
            )
        except Exception as e:
            logger.warning(
                "Cache invalidation error for tenant %s: %s",
                tenant_id, e,
            )

    async def clear_all(self) -> None:
        """Clear all dashboard cache entries.

        Removes all keys with the "dashboard:" prefix.
        """
        if not self._enabled or not self._redis:
            return

        pattern = self._make_key("*")
        try:
            cursor = 0
            deleted_count = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break

            logger.info("Cleared all %d dashboard cache entries", deleted_count)
        except Exception as e:
            logger.warning("Cache clear error: %s", e)

    async def health_check(self) -> bool:
        """Check if the cache backend is healthy.

        Returns:
            True if cache is available and responsive.
        """
        if not self._enabled or not self._redis:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.warning("Cache health check failed: %s", e)
            return False
