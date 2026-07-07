"""Activity service for dashboard activity feed management.

Provides logging, retrieval, filtering, and pagination of
dashboard activity entries across all subsystems.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from regulaforge.config.logging import get_logger
from regulaforge.dashboard.domain.models import DashboardActivity
from regulaforge.dashboard.infrastructure.cache import DashboardCache
from regulaforge.dashboard.infrastructure.repository import (
    DashboardActivityRepository,
)

logger = get_logger(__name__)


class ActivityService:
    """Manages the dashboard activity feed.

    Provides functions to log new activities, retrieve recent
    activity, filter activity feeds, and get user-specific activity.
    """

    def __init__(
        self,
        repository: Optional[DashboardActivityRepository] = None,
        dashboard_cache: Optional[DashboardCache] = None,
    ) -> None:
        """Initialize ActivityService with dependencies.

        Args:
            repository: Activity repository for persistence.
            dashboard_cache: Cache instance for data caching.
        """
        self._repo = repository or DashboardActivityRepository()
        self._cache = dashboard_cache or DashboardCache()

    async def log_activity(
        self,
        activity_type: str,
        description: str,
        user_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        severity: str = "info",
        metadata: Optional[dict[str, Any]] = None,
    ) -> DashboardActivity:
        """Log a new activity entry.

        Creates and persists a new activity record in the
        dashboard activity feed.

        Args:
            activity_type: Type/category of activity.
            description: Human-readable activity description.
            user_id: User who performed the activity (optional).
            entity_id: Related entity identifier (optional).
            severity: Severity level ('info', 'warning', 'critical').
            metadata: Additional structured data (optional).

        Returns:
            The created DashboardActivity.
        """
        now = datetime.now(timezone.utc)
        activity = DashboardActivity(
            id=str(uuid4()),
            timestamp=now,
            activity_type=activity_type,
            description=description,
            user_id=user_id,
            entity_id=entity_id,
            severity=severity,
            metadata=metadata or {},
        )

        await self._repo.save(activity)
        logger.info(
            "Activity logged: %s (%s) by user %s",
            activity_type, severity, user_id,
        )

        return activity

    async def get_recent_activity(
        self,
        tenant_id: str,
        limit: int = 20,
    ) -> list[DashboardActivity]:
        """Get the most recent activity entries for a tenant.

        Args:
            tenant_id: The tenant identifier.
            limit: Maximum number of entries to return.

        Returns:
            List of recent DashboardActivity objects.
        """
        cache_key = f"recent_activity:{tenant_id}:{limit}"

        async def _compute() -> list[DashboardActivity]:
            logger.info(
                "Fetching recent activity for tenant %s (limit=%d)",
                tenant_id, limit,
            )
            return await self._repo.get_recent(tenant_id, limit)

        return await self._cache.get_cached_or_compute(
            cache_key, _compute, ttl=60
        )

    async def get_activity_feed(
        self,
        tenant_id: str,
        filters: Optional[dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Get paginated, filtered activity feed.

        Supports filtering by activity_type, severity, user_id,
        date range, and entity_id.

        Args:
            tenant_id: The tenant identifier.
            filters: Optional dict of filter criteria.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Dict with items, total, page, page_size, total_pages.
        """
        filters = filters or {}
        logger.info(
            "Fetching activity feed for tenant %s (page=%d, page_size=%d)",
            tenant_id, page, page_size,
        )

        items, total = await self._repo.get_filtered(
            tenant_id, filters, page, page_size,
        )
        total_pages = max(1, -(-total // page_size))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def get_user_activity(
        self,
        user_id: str,
        days: int = 7,
    ) -> list[DashboardActivity]:
        """Get activity for a specific user over a period.

        Args:
            user_id: The user identifier.
            days: Number of days of history.

        Returns:
            List of DashboardActivity objects for the user.
        """
        logger.info(
            "Fetching activity for user %s (%dd)",
            user_id, days,
        )
        return await self._repo.get_by_user(user_id, days)
