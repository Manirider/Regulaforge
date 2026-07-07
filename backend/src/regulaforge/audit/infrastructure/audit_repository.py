"""SQLAlchemy-based repository for audit log persistence.

Implements the audit log data access layer with support for
filtered search, pagination, and batch export operations.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.audit.domain.audit_entry import AuditEntry
from regulaforge.audit.infrastructure.models import AuditLogModel
from regulaforge.config.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, AuditAction
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyAuditRepository:
    """Repository for persisting and querying audit log entries.

    Provides save, search, count, and batch export operations
    using SQLAlchemy async sessions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entry: AuditEntry) -> AuditEntry:
        """Persist a new audit entry.

        Args:
            entry: The audit entry to persist.

        Returns:
            The saved audit entry with any generated fields.

        Raises:
            RuntimeError: If the database operation fails.
        """
        try:
            model = AuditLogModel(
                id=entry.id,
                action=entry.action.value,
                actor_id=entry.actor_id,
                actor_email=entry.actor_email,
                tenant_id=entry.tenant_id,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                details=entry.details or {},
                changes=entry.changes or {},
                ip_address=entry.ip_address,
                user_agent=entry.user_agent,
                correlation_id=entry.correlation_id,
                timestamp=entry.timestamp,
            )
            self._session.add(model)
            await self._session.flush()
            logger.debug(
                "Audit entry saved: action=%s actor=%s resource=%s:%s",
                entry.action.value, entry.actor_email,
                entry.resource_type, entry.resource_id,
            )
            return entry
        except Exception as exc:
            logger.error("Failed to save audit entry: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to save audit entry: {exc}") from exc

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[AuditEntry], int]:
        """Search audit entries with filtering, sorting, and pagination.

        Args:
            filters: Dictionary of field filters. Supported keys:
                - action (AuditAction or str)
                - actor_id (UUID)
                - tenant_id (UUID)
                - resource_type (str)
                - resource_id (str)
                - correlation_id (str)
                - start_date (datetime)
                - end_date (datetime)
            sort_by: Field name to sort by.
            sort_order: 'asc' or 'desc'.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (audit entries list, total count).

        Raises:
            ValueError: If page or page_size are invalid.
        """
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

        try:
            query = self._build_search_query(filters or {})
            sort_column = getattr(AuditLogModel, sort_by, AuditLogModel.timestamp)
            order_fn = sort_column.desc if sort_order == "desc" else sort_column.asc
            ordered_query = query.order_by(order_fn())

            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self._session.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            paginated_query = ordered_query.offset(offset).limit(page_size)
            result = await self._session.execute(paginated_query)
            models = result.scalars().all()

            entries = [self._model_to_entry(model) for model in models]
            logger.debug(
                "Audit search returned %d of %d results (page=%d, page_size=%d)",
                len(entries), total_count, page, page_size,
            )
            return entries, total_count
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to search audit entries: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to search audit entries: {exc}") from exc

    async def count(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> int:
        """Count audit entries matching the given filters.

        Args:
            filters: Dictionary of field filters (same as search).

        Returns:
            Total count of matching entries.

        Raises:
            RuntimeError: If the database operation fails.
        """
        try:
            query = self._build_search_query(filters or {})
            count_query = select(func.count()).select_from(query.subquery())
            result = await self._session.execute(count_query)
            return result.scalar_one()
        except Exception as exc:
            logger.error("Failed to count audit entries: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to count audit entries: {exc}") from exc

    async def export_batch(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
        batch_size: int = 1000,
    ) -> str:
        """Export audit entries for a tenant as CSV within a date range.

        Uses server-side cursors for memory-efficient streaming
        of large result sets.

        Args:
            tenant_id: The tenant UUID to export.
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (exclusive).
            batch_size: Number of records to fetch per batch.

        Returns:
            CSV-formatted string of audit entries.

        Raises:
            ValueError: If date range is invalid.
            RuntimeError: If the export fails.
        """
        if start_date >= end_date:
            raise ValueError("start_date must be before end_date")

        try:
            query = (
                select(AuditLogModel)
                .where(
                    and_(
                        AuditLogModel.tenant_id == tenant_id,
                        AuditLogModel.timestamp >= start_date,
                        AuditLogModel.timestamp < end_date,
                    )
                )
                .order_by(AuditLogModel.timestamp.asc())
            )

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "id", "action", "actor_id", "actor_email", "tenant_id",
                "resource_type", "resource_id", "details", "changes",
                "ip_address", "user_agent", "correlation_id", "timestamp",
            ])

            offset = 0
            while True:
                batch_query = query.offset(offset).limit(batch_size)
                result = await self._session.execute(batch_query)
                models = result.scalars().all()

                if not models:
                    break

                for model in models:
                    writer.writerow([
                        str(model.id),
                        model.action,
                        str(model.actor_id),
                        model.actor_email,
                        str(model.tenant_id),
                        model.resource_type,
                        model.resource_id,
                        str(model.details or {}),
                        str(model.changes or {}),
                        model.ip_address or "",
                        model.user_agent or "",
                        model.correlation_id or "",
                        model.timestamp.isoformat(),
                    ])

                offset += len(models)
                logger.debug(
                    "Export batch: %d records written (offset=%d)",
                    len(models), offset,
                )

            csv_content = output.getvalue()
            output.close()
            logger.info(
                "Audit export completed: tenant=%s, range=%s..%s, total=%d",
                tenant_id, start_date.isoformat(), end_date.isoformat(), offset,
            )
            return csv_content
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to export audit entries: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to export audit entries: {exc}") from exc

    def _build_search_query(self, filters: dict[str, Any]) -> Select:
        """Build a SELECT query from the given filters.

        Args:
            filters: Dictionary of filter criteria.

        Returns:
            A SQLAlchemy Select statement.
        """
        conditions = []

        action = filters.get("action")
        if action is not None:
            if isinstance(action, AuditAction):
                conditions.append(AuditLogModel.action == action.value)
            else:
                conditions.append(AuditLogModel.action == str(action))

        actor_id = filters.get("actor_id")
        if actor_id is not None:
            conditions.append(AuditLogModel.actor_id == actor_id)

        tenant_id = filters.get("tenant_id")
        if tenant_id is not None:
            conditions.append(AuditLogModel.tenant_id == tenant_id)

        resource_type = filters.get("resource_type")
        if resource_type is not None:
            conditions.append(AuditLogModel.resource_type == resource_type)

        resource_id = filters.get("resource_id")
        if resource_id is not None:
            conditions.append(AuditLogModel.resource_id == resource_id)

        correlation_id = filters.get("correlation_id")
        if correlation_id is not None:
            conditions.append(AuditLogModel.correlation_id == correlation_id)

        start_date = filters.get("start_date")
        if start_date is not None:
            conditions.append(AuditLogModel.timestamp >= start_date)

        end_date = filters.get("end_date")
        if end_date is not None:
            conditions.append(AuditLogModel.timestamp < end_date)

        return select(AuditLogModel).where(and_(*conditions)) if conditions else select(AuditLogModel)

    @staticmethod
    def _model_to_entry(model: AuditLogModel) -> AuditEntry:
        """Convert an ORM model instance to a domain AuditEntry.

        Args:
            model: The SQLAlchemy model instance.

        Returns:
            The corresponding AuditEntry domain object.
        """
        return AuditEntry.create(
            id=model.id,
            action=AuditAction(model.action),
            actor_id=model.actor_id,
            actor_email=model.actor_email,
            tenant_id=model.tenant_id,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            details=model.details or {},
            changes=model.changes or {},
            ip_address=model.ip_address,
            user_agent=model.user_agent,
            correlation_id=model.correlation_id,
            timestamp=model.timestamp,
        )
