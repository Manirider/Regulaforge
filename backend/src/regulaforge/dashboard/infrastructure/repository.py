"""SQLAlchemy repository implementations for dashboard domain models.

Provides data access layer for dashboard configurations, compliance
snapshots, and activity records using SQLAlchemy async sessions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select

from regulaforge.config.logging import get_logger
from regulaforge.dashboard.domain.models import (
    ComplianceSnapshot,
    DashboardActivity,
    DashboardConfig,
    DashboardWidget,
)
from regulaforge.dashboard.infrastructure.models import (
    ComplianceSnapshotModel,
    DashboardActivityModel,
    DashboardConfigModel,
)
from regulaforge.infrastructure.persistence.database import get_session

logger = get_logger(__name__)


class DashboardConfigRepository:
    """Repository for dashboard configuration persistence."""

    async def get_by_id(self, config_id: str) -> Optional[DashboardConfig]:
        """Get a dashboard configuration by its ID.

        Args:
            config_id: The configuration identifier.

        Returns:
            DashboardConfig if found, None otherwise.
        """
        async for session in get_session():
            stmt = select(DashboardConfigModel).where(
                DashboardConfigModel.id == UUID(config_id)
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return None
            return self._model_to_domain(model)

    async def get_by_tenant(
        self,
        tenant_id: str,
        include_default: bool = True,
    ) -> list[DashboardConfig]:
        """Get all dashboard configurations for a tenant.

        Args:
            tenant_id: The tenant identifier.
            include_default: Whether to include the default config.

        Returns:
            List of DashboardConfig objects.
        """
        async for session in get_session():
            stmt = select(DashboardConfigModel).where(
                DashboardConfigModel.tenant_id == UUID(tenant_id)
            )
            if not include_default:
                stmt = stmt.where(DashboardConfigModel.is_default == False)  # noqa: E712
            stmt = stmt.order_by(DashboardConfigModel.created_at.desc())
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]

    async def get_default(self, tenant_id: str) -> Optional[DashboardConfig]:
        """Get the default dashboard configuration for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            Default DashboardConfig if found, None otherwise.
        """
        async for session in get_session():
            stmt = select(DashboardConfigModel).where(
                and_(
                    DashboardConfigModel.tenant_id == UUID(tenant_id),
                    DashboardConfigModel.is_default == True,  # noqa: E712
                )
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return None
            return self._model_to_domain(model)

    async def save(self, config: DashboardConfig) -> str:
        """Save a new dashboard configuration.

        Args:
            config: The DashboardConfig domain object.

        Returns:
            The saved configuration identifier.
        """
        async for session in get_session():
            model = DashboardConfigModel(
                id=UUID(config.id) if config.id else uuid4(),
                name=config.name,
                description=config.description,
                layout=[w.__dict__ for w in config.layout],
                tenant_id=UUID(config.tenant_id),
                created_by=UUID(config.created_by) if config.created_by else None,
                is_default=config.is_default,
                sharing_config=config.sharing_config,
            )
            session.add(model)
            await session.flush()
            logger.info("Dashboard config %s saved for tenant %s", model.id, config.tenant_id)
            return str(model.id)

    async def update(self, config_id: str, updates: dict[str, Any]) -> Optional[DashboardConfig]:
        """Update an existing dashboard configuration.

        Args:
            config_id: The configuration identifier.
            updates: Dict of fields to update.

        Returns:
            Updated DashboardConfig if found, None otherwise.
        """
        async for session in get_session():
            stmt = select(DashboardConfigModel).where(
                DashboardConfigModel.id == UUID(config_id)
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return None

            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            await session.flush()
            logger.info("Dashboard config %s updated", config_id)
            return self._model_to_domain(model)

    def _model_to_domain(self, model: DashboardConfigModel) -> DashboardConfig:
        """Convert a SQLAlchemy model to a domain DashboardConfig.

        Args:
            model: The SQLAlchemy model instance.

        Returns:
            Corresponding DashboardConfig domain object.
        """
        widgets = [
            DashboardWidget(**w) if isinstance(w, dict) else w
            for w in (model.layout or [])
        ]
        return DashboardConfig(
            id=str(model.id),
            name=model.name,
            description=model.description,
            layout=widgets,
            tenant_id=str(model.tenant_id),
            created_by=str(model.created_by) if model.created_by else None,
            is_default=model.is_default,
            sharing_config=model.sharing_config or {},
        )


class ComplianceSnapshotRepository:
    """Repository for compliance snapshot persistence."""

    async def get_by_id(self, snapshot_id: str) -> Optional[ComplianceSnapshot]:
        """Get a snapshot by its ID.

        Args:
            snapshot_id: The snapshot identifier.

        Returns:
            ComplianceSnapshot if found, None otherwise.
        """
        async for session in get_session():
            stmt = select(ComplianceSnapshotModel).where(
                ComplianceSnapshotModel.id == UUID(snapshot_id)
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return None
            return self._model_to_domain(model)

    async def get_latest(self, tenant_id: str) -> Optional[ComplianceSnapshot]:
        """Get the most recent snapshot for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            Most recent ComplianceSnapshot if any exist.
        """
        async for session in get_session():
            stmt = (
                select(ComplianceSnapshotModel)
                .where(ComplianceSnapshotModel.tenant_id == UUID(tenant_id))
                .order_by(ComplianceSnapshotModel.timestamp.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return None
            return self._model_to_domain(model)

    async def get_history(
        self,
        tenant_id: str,
        days: int = 90,
    ) -> list[ComplianceSnapshot]:
        """Get snapshot history for a tenant over a period.

        Args:
            tenant_id: The tenant identifier.
            days: Number of days of history.

        Returns:
            List of ComplianceSnapshot objects in chronological order.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        async for session in get_session():
            stmt = (
                select(ComplianceSnapshotModel)
                .where(
                    and_(
                        ComplianceSnapshotModel.tenant_id == UUID(tenant_id),
                        ComplianceSnapshotModel.timestamp >= since,
                    )
                )
                .order_by(ComplianceSnapshotModel.timestamp.asc())
            )
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]

    async def save(
        self,
        snapshot: ComplianceSnapshot,
        tenant_id: str,
    ) -> str:
        """Save a new compliance snapshot.

        Args:
            snapshot: The ComplianceSnapshot domain object.
            tenant_id: The tenant identifier.

        Returns:
            The saved snapshot identifier.
        """
        async for session in get_session():
            model = ComplianceSnapshotModel(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                timestamp=snapshot.timestamp,
                overall_compliance_rate=snapshot.overall_compliance_rate,
                entities_assessed=snapshot.entities_assessed,
                entities_in_scope=snapshot.entities_in_scope,
                findings_by_severity=snapshot.findings_by_severity,
                overdue_assessments=snapshot.overdue_assessments,
                regulations_tracked=snapshot.regulations_tracked,
                active_alerts=snapshot.active_alerts,
                risk_distribution=snapshot.risk_distribution,
                top_risk_factors=snapshot.top_risk_factors,
                recent_changes=snapshot.recent_changes,
            )
            session.add(model)
            await session.flush()
            logger.info(
                "Compliance snapshot %s saved for tenant %s",
                model.id, tenant_id,
            )
            return str(model.id)

    def _model_to_domain(
        self,
        model: ComplianceSnapshotModel,
    ) -> ComplianceSnapshot:
        """Convert a SQLAlchemy model to a domain ComplianceSnapshot.

        Args:
            model: The SQLAlchemy model instance.

        Returns:
            Corresponding ComplianceSnapshot domain object.
        """
        return ComplianceSnapshot(
            timestamp=model.timestamp,
            overall_compliance_rate=model.overall_compliance_rate,
            entities_assessed=model.entities_assessed,
            entities_in_scope=model.entities_in_scope,
            findings_by_severity=model.findings_by_severity or {},
            overdue_assessments=model.overdue_assessments,
            regulations_tracked=model.regulations_tracked,
            active_alerts=model.active_alerts,
            risk_distribution=model.risk_distribution or {},
            top_risk_factors=model.top_risk_factors or [],
            recent_changes=model.recent_changes or [],
        )


class DashboardActivityRepository:
    """Repository for dashboard activity feed persistence."""

    async def save(self, activity: DashboardActivity) -> str:
        """Save a new activity entry.

        Args:
            activity: The DashboardActivity domain object.

        Returns:
            The saved activity identifier.
        """
        async for session in get_session():
            model = DashboardActivityModel(
                id=UUID(activity.id),
                tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
                timestamp=activity.timestamp,
                activity_type=activity.activity_type,
                description=activity.description,
                user_id=UUID(activity.user_id) if activity.user_id else None,
                entity_id=activity.entity_id,
                severity=activity.severity,
                metadata=activity.metadata,
            )
            session.add(model)
            await session.flush()
            return str(model.id)

    async def get_recent(
        self,
        tenant_id: str,
        limit: int = 20,
    ) -> list[DashboardActivity]:
        """Get the most recent activity entries for a tenant.

        Args:
            tenant_id: The tenant identifier.
            limit: Maximum number of entries.

        Returns:
            List of recent DashboardActivity objects.
        """
        async for session in get_session():
            stmt = (
                select(DashboardActivityModel)
                .where(DashboardActivityModel.tenant_id == UUID(tenant_id))
                .order_by(DashboardActivityModel.timestamp.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]

    async def get_filtered(
        self,
        tenant_id: str,
        filters: dict[str, Any],
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DashboardActivity], int]:
        """Get filtered and paginated activity entries.

        Args:
            tenant_id: The tenant identifier.
            filters: Dict with filter criteria (activity_type, severity,
                user_id, entity_id, date_from, date_to).
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of DashboardActivity, total count).
        """
        async for session in get_session():
            base_query = select(DashboardActivityModel).where(
                DashboardActivityModel.tenant_id == UUID(tenant_id)
            )

            if "activity_type" in filters:
                base_query = base_query.where(
                    DashboardActivityModel.activity_type == filters["activity_type"]
                )
            if "severity" in filters:
                base_query = base_query.where(
                    DashboardActivityModel.severity == filters["severity"]
                )
            if "user_id" in filters:
                base_query = base_query.where(
                    DashboardActivityModel.user_id == UUID(filters["user_id"])
                )
            if "entity_id" in filters:
                base_query = base_query.where(
                    DashboardActivityModel.entity_id == filters["entity_id"]
                )
            if "date_from" in filters:
                base_query = base_query.where(
                    DashboardActivityModel.timestamp >= filters["date_from"]
                )
            if "date_to" in filters:
                base_query = base_query.where(
                    DashboardActivityModel.timestamp <= filters["date_to"]
                )

            count_stmt = select(func.count()).select_from(base_query.subquery())
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            offset = (page - 1) * page_size
            stmt = (
                base_query
                .order_by(DashboardActivityModel.timestamp.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            models = result.scalars().all()

            return [self._model_to_domain(m) for m in models], total

    async def get_by_user(
        self,
        user_id: str,
        days: int = 7,
    ) -> list[DashboardActivity]:
        """Get activity entries for a specific user.

        Args:
            user_id: The user identifier.
            days: Number of days of history.

        Returns:
            List of DashboardActivity objects for the user.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        async for session in get_session():
            stmt = (
                select(DashboardActivityModel)
                .where(
                    and_(
                        DashboardActivityModel.user_id == UUID(user_id),
                        DashboardActivityModel.timestamp >= since,
                    )
                )
                .order_by(DashboardActivityModel.timestamp.desc())
            )
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]

    def _model_to_domain(
        self,
        model: DashboardActivityModel,
    ) -> DashboardActivity:
        """Convert a SQLAlchemy model to a domain DashboardActivity.

        Args:
            model: The SQLAlchemy model instance.

        Returns:
            Corresponding DashboardActivity domain object.
        """
        return DashboardActivity(
            id=str(model.id),
            timestamp=model.timestamp,
            activity_type=model.activity_type,
            description=model.description,
            user_id=str(model.user_id) if model.user_id else None,
            entity_id=model.entity_id,
            severity=model.severity,
            metadata=model.metadata or {},
        )
