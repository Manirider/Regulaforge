"""Cache port interface.

Defines the contract for caching operations that infrastructure
adapters (e.g. RedisCache) must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional


class CachePort(ABC):
    """Abstract port interface for caching operations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Retrieve a value by key.

        Args:
            key: Cache key.

        Returns:
            The cached string value, or None if not found/expired.
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Store a value with an optional time-to-live.

        Args:
            key: Cache key.
            value: Cache value.
            ttl: Time-to-live in seconds.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a value from the cache.

        Args:
            key: Cache key.
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: Cache key.

        Returns:
            True if the key exists and is not expired, False otherwise.
        """
        ...

    @abstractmethod
    async def get_many(self, *keys: str) -> dict[str, str]:
        """Retrieve multiple values by keys.

        Args:
            keys: Variable list of cache keys.

        Returns:
            A dictionary mapping found keys to their values.
        """
        ...

    @abstractmethod
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching the given glob/redis pattern.

        Args:
            pattern: Pattern string (e.g. ``"regulation:*"``).

        Returns:
            The number of keys invalidated.
        """
        ...
