"""Redis-based rate limiter using the token bucket algorithm.

Provides configurable rate limiting per client key with
smooth token bucket semantics for API protection.
"""

import time
from typing import Optional

import redis.asyncio as aioredis

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)

# Lua script for atomic token bucket operations
_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])
local refill_interval = tonumber(ARGV[4])
local cost = tonumber(ARGV[5])

-- Get current state
local state = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(state[1])
local last_refill = tonumber(state[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- Calculate refill since last check
local elapsed = now - last_refill
local refill_count = math.floor(elapsed / refill_interval)
if refill_count > 0 then
    local refill_tokens = refill_count * refill_rate
    tokens = math.min(capacity, tokens + refill_tokens)
    last_refill = last_refill + (refill_count * refill_interval)
end

-- Check if request can proceed
if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    local ttl = math.ceil(capacity / refill_rate * refill_interval * 2)
    redis.call('EXPIRE', key, ttl)
    return {1, tokens, math.max(0, tokens)}
else
    local retry_after = math.ceil((cost - tokens) / refill_rate) * refill_interval
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    local ttl = math.ceil(capacity / refill_rate * refill_interval * 2)
    redis.call('EXPIRE', key, ttl)
    return {0, tokens, retry_after}
end
"""


class RateLimitResult:
    """Result of a rate limit check."""

    def __init__(
        self,
        allowed: bool,
        remaining: int,
        retry_after: int = 0,
        limit: int = 0,
    ) -> None:
        self.allowed = allowed
        self.remaining = remaining
        self.retry_after = retry_after
        self.limit = limit

    def __repr__(self) -> str:
        return (
            f"<RateLimitResult allowed={self.allowed} "
            f"remaining={self.remaining}/{self.limit}>"
        )


class TokenBucketRateLimiter:
    """Redis-backed token bucket rate limiter.

    Each client key gets a bucket with:
    - capacity: maximum burst size
    - refill_rate: tokens added per refill_interval
    - refill_interval: time between refills (seconds)

    Thread-safe via atomic Lua scripts on the Redis server.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        capacity: int = settings.security.rate_limit_per_minute,
        refill_rate: int = 1,
        refill_interval: float = 1.0,
        key_prefix: str = "ratelimit:",
    ) -> None:
        self._redis = redis_client
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._refill_interval = refill_interval
        self._key_prefix = key_prefix
        self._sha: Optional[str] = None

    async def _load_script(self) -> str:
        """Load the Lua script into Redis and cache its SHA."""
        if not self._sha:
            self._sha = await self._redis.script_load(_TOKEN_BUCKET_SCRIPT)
        return self._sha

    def _build_key(self, client_key: str) -> str:
        """Build the Redis key for a client."""
        return f"{self._key_prefix}{client_key}"

    async def check_rate_limit(
        self,
        client_key: str,
        cost: int = 1,
    ) -> RateLimitResult:
        """Check if a request is within the rate limit.

        Args:
            client_key: Unique identifier for the client (IP, user ID, API key).
            cost: Number of tokens to consume (default 1).

        Returns:
            A RateLimitResult with allowed status and metadata.
        """
        if cost < 1:
            raise ValueError("Cost must be at least 1")

        try:
            redis_key = self._build_key(client_key)
            now = time.time()
            sha = await self._load_script()

            result = await self._redis.evalsha(
                sha,
                1,
                redis_key,
                str(now),
                str(self._capacity),
                str(self._refill_rate),
                str(self._refill_interval),
                str(cost),
            )

            allowed = bool(result[0])
            remaining = int(result[1])
            retry_after = int(result[2])

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                retry_after=retry_after,
                limit=self._capacity,
            )
        except Exception as e:
            logger.error("Rate limit check failed for %s: %s", client_key, e)
            # Fail open: allow the request if Redis is unavailable
            return RateLimitResult(
                allowed=True,
                remaining=self._capacity,
                limit=self._capacity,
            )

    async def get_remaining(self, client_key: str) -> int:
        """Get the remaining tokens for a client without consuming.

        Args:
            client_key: Unique identifier for the client.

        Returns:
            Number of remaining tokens.
        """
        try:
            redis_key = self._build_key(client_key)
            state = await self._redis.hmget(redis_key, "tokens", "last_refill")
            tokens = int(state[0]) if state[0] else self._capacity
            last_refill = float(state[1]) if state[1] else time.time()

            elapsed = time.time() - last_refill
            refill_count = int(elapsed / self._refill_interval)
            if refill_count > 0:
                refill_tokens = refill_count * self._refill_rate
                tokens = min(self._capacity, tokens + refill_tokens)

            return int(tokens)
        except Exception as e:
            logger.error("Failed to get remaining for %s: %s", client_key, e)
            return self._capacity

    async def reset(self, client_key: str) -> None:
        """Reset the rate limit bucket for a client.

        Args:
            client_key: Unique identifier for the client.
        """
        try:
            redis_key = self._build_key(client_key)
            await self._redis.delete(redis_key)
            logger.debug("Rate limit reset for %s", client_key)
        except Exception as e:
            logger.error("Failed to reset rate limit for %s: %s", client_key, e)

    async def close(self) -> None:
        """Clean up Redis resources."""
        try:
            await self._redis.close()
        except Exception as e:
            logger.error("Failed to close rate limiter Redis client: %s", e)
