"""Application service for audit trail management.

Provides the public API for logging audit entries, querying the
audit trail, and exporting audit data for compliance purposes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.audit.domain.audit_entry import AuditEntry
from regulaforge.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from regulaforge.config.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, AuditAction
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class PaginatedResult:
    """Generic paginated result container."""

    def __init__(
        self,
        items: list[AuditEntry],
        total: int,
        page: int,
        page_size: int,
    ) -> None:
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = max(1, (total + page_size - 1) // page_size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "pagination": {
                "page": self.page,
                "page_size": self.page_size,
                "total": self.total,
                "total_pages": self.total_pages,
            },
        }


class AuditService:
    """Application service for audit trail operations.

    Provides methods for logging actions, querying the audit trail,
    and exporting audit data. Coordinates between the domain layer
    and infrastructure persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repository = SqlAlchemyAuditRepository(session)

    async def log_action(
        self,
        action: AuditAction,
        actor_id: UUID,
        actor_email: str,
        tenant_id: UUID,
        resource_type: str,
        resource_id: str,
        details: Optional[dict[str, Any]] = None,
        changes: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditEntry:
        """Log an auditable action to the audit trail.

        Creates an AuditEntry with the given parameters and
        persists it via the repository.

        Args:
            action: The auditable action performed.
            actor_id: UUID of the acting user.
            actor_email: Email of the acting user.
            tenant_id: Tenant context UUID.
            resource_type: Type of resource affected.
            resource_id: Identifier of the specific resource.
            details: Free-form details about the action.
            changes: Old/new value pairs for change tracking.
            ip_address: Source IP address of the request.
            user_agent: User agent string from the request.
            correlation_id: Distributed tracing correlation ID.

        Returns:
            The persisted AuditEntry.

        Raises:
            RuntimeError: If persistence fails.
        """
        try:
            entry = AuditEntry.create(
                action=action,
                actor_id=actor_id,
                actor_email=actor_email,
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                changes=changes,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
            )

            saved_entry = await self._repository.save(entry)
            logger.info(
                "Audit action logged: %s by %s on %s:%s [tenant=%s]",
                action.value, actor_email, resource_type, resource_id, tenant_id,
            )
            return saved_entry
        except Exception as exc:
            logger.error("Failed to log audit action: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to log audit action: {exc}") from exc

    async def get_audit_trail(
        self,
        resource_type: str,
        resource_id: str,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult:
        """Get the audit trail for a specific resource.

        Args:
            resource_type: Type of resource.
            resource_id: Identifier of the resource.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            PaginatedResult with matching audit entries.

        Raises:
            ValueError: If pagination parameters are invalid.
            RuntimeError: If the query fails.
        """
        try:
            filters = {
                "resource_type": resource_type,
                "resource_id": resource_id,
            }
            entries, total = await self._repository.search(
                filters=filters,
                sort_by="timestamp",
                sort_order="desc",
                page=page,
                page_size=page_size,
            )
            logger.debug(
                "Audit trail query: resource=%s:%s, page=%d, total=%d",
                resource_type, resource_id, page, total,
            )
            return PaginatedResult(
                items=entries,
                total=total,
                page=page,
                page_size=page_size,
            )
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to retrieve audit trail: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to retrieve audit trail: {exc}") from exc

    async def get_actor_history(
        self,
        actor_id: UUID,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult:
        """Get the audit history for a specific actor.

        Args:
            actor_id: UUID of the actor to query.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            PaginatedResult with matching audit entries.

        Raises:
            ValueError: If pagination parameters are invalid.
            RuntimeError: If the query fails.
        """
        try:
            filters = {"actor_id": actor_id}
            entries, total = await self._repository.search(
                filters=filters,
                sort_by="timestamp",
                sort_order="desc",
                page=page,
                page_size=page_size,
            )
            logger.debug(
                "Actor history query: actor=%s, page=%d, total=%d",
                actor_id, page, total,
            )
            return PaginatedResult(
                items=entries,
                total=total,
                page=page,
                page_size=page_size,
            )
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to retrieve actor history: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to retrieve actor history: {exc}") from exc

    async def get_tenant_audit_log(
        self,
        tenant_id: UUID,
        filters: Optional[dict[str, Any]] = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult:
        """Get the full audit log for a tenant with optional filtering.

        Args:
            tenant_id: The tenant UUID.
            filters: Additional filter criteria (action, date range, etc.).
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            PaginatedResult with matching audit entries.

        Raises:
            ValueError: If pagination parameters are invalid.
            RuntimeError: If the query fails.
        """
        try:
            query_filters: dict[str, Any] = {"tenant_id": tenant_id}
            if filters:
                query_filters.update(filters)

            entries, total = await self._repository.search(
                filters=query_filters,
                sort_by="timestamp",
                sort_order="desc",
                page=page,
                page_size=page_size,
            )
            logger.debug(
                "Tenant audit log query: tenant=%s, page=%d, total=%d",
                tenant_id, page, total,
            )
            return PaginatedResult(
                items=entries,
                total=total,
                page=page,
                page_size=page_size,
            )
        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "Failed to retrieve tenant audit log: %s", exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to retrieve tenant audit log: {exc}") from exc

    async def export_audit_log(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
        format: str = "csv",
    ) -> str:
        """Export the tenant audit log as a downloadable file.

        Args:
            tenant_id: The tenant UUID to export.
            start_date: Start of date range (inclusive).
            end_date: End of date range (exclusive).
            format: Export format ("csv" only currently supported).

        Returns:
            String content of the exported file.

        Raises:
            ValueError: If date range or format is invalid.
            RuntimeError: If the export fails.
        """
        if format != "csv":
            raise ValueError(f"Unsupported export format: {format}. Only 'csv' is supported.")

        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        try:
            csv_content = await self._repository.export_batch(
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
            )
            logger.info(
                "Audit log exported: tenant=%s, format=%s, range=%s..%s",
                tenant_id, format, start_date.isoformat(), end_date.isoformat(),
            )
            return csv_content
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to export audit log: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to export audit log: {exc}") from exc
