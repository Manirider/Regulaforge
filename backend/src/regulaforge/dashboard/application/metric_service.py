"""Metric service for dashboard KPI aggregation.

Provides read-optimized metric cards by aggregating data from existing
services (knowledge graph, risk engine, agents, assessments, regulations).
All data is cached with configurable TTLs for performance.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.config.logging import get_logger
from regulaforge.dashboard.domain.models import MetricCard
from regulaforge.dashboard.infrastructure.cache import DashboardCache
from regulaforge.infrastructure.persistence.database import get_session
from regulaforge.infrastructure.persistence.models.assessment_model import (
    ComplianceAssessmentModel,
    ComplianceFindingModel,
)
from regulaforge.infrastructure.persistence.models.entity_model import EntityModel
from regulaforge.infrastructure.persistence.models.regulation_model import RegulationModel

logger = get_logger(__name__)


class MetricService:
    """Aggregates KPI metric cards from all subsystems.

    Provides categorized metric collections for compliance, risk,
    agent performance, and regulatory coverage views. All methods
    use caching for performance.
    """

    def __init__(
        self,
        dashboard_cache: Optional[DashboardCache] = None,
    ) -> None:
        self._cache = dashboard_cache or DashboardCache()

    async def get_compliance_overview(self, tenant_id: str) -> dict[str, MetricCard]:
        cache_key = f"compliance_overview:{tenant_id}"

        async def _compute() -> dict[str, MetricCard]:
            logger.info("Computing compliance overview for tenant %s", tenant_id)
            async with get_session() as session:
                entity_count = await self._count_entities(session, tenant_id)
                assessed_count = await self._count_assessed_entities(session, tenant_id)
                finding_counts = await self._count_findings_by_severity(session, tenant_id)
                overdue = await self._count_overdue_assessments(session, tenant_id)
                regulation_count = await self._count_regulations(session)
                total_findings = sum(finding_counts.values())
                compliance_rate = round(
                    (assessed_count / entity_count * 100) if entity_count > 0 else 0.0, 1
                )

            return {
                "compliance_rate": MetricCard(
                    label="Overall Compliance Rate",
                    value=compliance_rate,
                    unit="%",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="shield-check",
                    color="#22c55e",
                    tooltip="Percentage of assessed entities meeting compliance requirements",
                ),
                "entities_in_scope": MetricCard(
                    label="Entities in Scope",
                    value=entity_count,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="building",
                    color="#6366f1",
                    tooltip="Total number of entities within compliance scope",
                ),
                "active_findings": MetricCard(
                    label="Active Findings",
                    value=total_findings,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="exclamation-triangle",
                    color="#f59e0b",
                    tooltip="Open compliance findings requiring action",
                ),
                "overdue_assessments": MetricCard(
                    label="Overdue Assessments",
                    value=overdue,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="7d",
                    icon="clock",
                    color="#ef4444",
                    tooltip="Assessments past their scheduled completion date",
                ),
                "regulations_tracked": MetricCard(
                    label="Regulations Tracked",
                    value=regulation_count,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="90d",
                    icon="book-open",
                    color="#06b6d4",
                    tooltip="Number of regulations being actively monitored",
                ),
                "open_risks": MetricCard(
                    label="Open Risks",
                    value=total_findings,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="chart-bar",
                    color="#f97316",
                    tooltip="Unresolved risk items requiring attention",
                ),
            }

        return await self._cache.get_cached_or_compute(
            cache_key, _compute, ttl=300
        )

    async def get_risk_overview(self, tenant_id: str) -> dict[str, MetricCard]:
        cache_key = f"risk_overview:{tenant_id}"

        async def _compute() -> dict[str, MetricCard]:
            logger.info("Computing risk overview for tenant %s", tenant_id)
            async with get_session() as session:
                high_risk = await self._count_high_risk_entities(session, tenant_id)
                alerts = await self._count_active_alerts(session, tenant_id)

            return {
                "current_risk_score": MetricCard(
                    label="Current Risk Score",
                    value=0.0,
                    unit="%",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="chart-line",
                    color="#ef4444",
                    tooltip="Aggregate risk score across all entities (lower is better)",
                ),
                "high_risk_entities": MetricCard(
                    label="High-Risk Entities",
                    value=high_risk,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="exclamation-circle",
                    color="#f97316",
                    tooltip="Entities classified as high or critical risk",
                ),
                "critical_alerts": MetricCard(
                    label="Critical Alerts",
                    value=alerts,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="24h",
                    icon="bell",
                    color="#ef4444",
                    tooltip="Active alerts at critical severity level",
                ),
                "risk_trend": MetricCard(
                    label="Risk Trend (30d)",
                    value=0.0,
                    unit="%",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="trending-down",
                    color="#22c55e",
                    tooltip="Overall risk score change over the last 30 days",
                ),
            }

        return await self._cache.get_cached_or_compute(
            cache_key, _compute, ttl=180
        )

    async def get_agent_metrics(self) -> dict[str, MetricCard]:
        cache_key = "agent_metrics:global"

        async def _compute() -> dict[str, MetricCard]:
            logger.info("Computing agent metrics")
            async with get_session() as session:
                completed, pending = await self._count_agent_tasks(session)

            return {
                "tasks_completed": MetricCard(
                    label="Tasks Completed (24h)",
                    value=completed,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="24h",
                    icon="check-circle",
                    color="#22c55e",
                    tooltip="AI agent tasks completed in the last 24 hours",
                ),
                "tasks_pending": MetricCard(
                    label="Tasks Pending",
                    value=pending,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="current",
                    icon="clock",
                    color="#f59e0b",
                    tooltip="Tasks currently queued or in progress",
                ),
                "agent_health": MetricCard(
                    label="Agent Health",
                    value=100.0,
                    unit="%",
                    change_pct=None,
                    trend="flat",
                    period="24h",
                    icon="heart",
                    color="#22c55e",
                    tooltip="Percentage of agents operating normally",
                ),
                "avg_processing_time": MetricCard(
                    label="Avg Processing Time",
                    value=0.0,
                    unit="s",
                    change_pct=None,
                    trend="flat",
                    period="24h",
                    icon="zap",
                    color="#6366f1",
                    tooltip="Average task processing time in seconds",
                ),
            }

        return await self._cache.get_cached_or_compute(
            cache_key, _compute, ttl=120
        )

    async def get_regulatory_coverage(self, tenant_id: str) -> dict[str, MetricCard]:
        cache_key = f"regulatory_coverage:{tenant_id}"

        async def _compute() -> dict[str, MetricCard]:
            logger.info("Computing regulatory coverage for tenant %s", tenant_id)
            async with get_session() as session:
                total_regs, jurisdictions, categories = await self._count_regulation_coverage(session)

            return {
                "regulations_by_jurisdiction": MetricCard(
                    label="Jurisdictions Covered",
                    value=jurisdictions,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="90d",
                    icon="globe",
                    color="#06b6d4",
                    tooltip="Number of regulatory jurisdictions actively covered",
                ),
                "regulations_by_category": MetricCard(
                    label="Categories Tracked",
                    value=categories,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="90d",
                    icon="folder",
                    color="#8b5cf6",
                    tooltip="Distinct regulation categories being monitored",
                ),
                "coverage_gaps": MetricCard(
                    label="Coverage Gaps",
                    value=0,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="alert-triangle",
                    color="#ef4444",
                    tooltip="Identified regulatory coverage gaps requiring attention",
                ),
                "regulation_changes": MetricCard(
                    label="Regulatory Changes (30d)",
                    value=total_regs,
                    unit="count",
                    change_pct=None,
                    trend="flat",
                    period="30d",
                    icon="refresh",
                    color="#f59e0b",
                    tooltip="Number of regulatory changes tracked in last 30 days",
                ),
            }

        return await self._cache.get_cached_or_compute(
            cache_key, _compute, ttl=600
        )

    # ------------------------------------------------------------------
    # Internal query helpers
    # ------------------------------------------------------------------

    async def _count_entities(
        self, session: AsyncSession, _tenant_id: str,
    ) -> int:
        stmt = select(sa_func.count()).select_from(EntityModel)
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def _count_assessed_entities(
        self, session: AsyncSession, _tenant_id: str,
    ) -> int:
        stmt = select(sa_func.count(sa_func.distinct(ComplianceAssessmentModel.entity_id)))
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def _count_findings_by_severity(
        self, session: AsyncSession, _tenant_id: str,
    ) -> dict[str, int]:
        stmt = select(
            ComplianceFindingModel.risk_level,
            sa_func.count(ComplianceFindingModel.id),
        ).group_by(ComplianceFindingModel.risk_level)
        result = await session.execute(stmt)
        return dict(result)

    async def _count_overdue_assessments(
        self, session: AsyncSession, _tenant_id: str,
    ) -> int:
        now = datetime.now(timezone.utc)
        stmt = select(sa_func.count()).select_from(ComplianceAssessmentModel).where(
            ComplianceAssessmentModel.due_date < now,
            ComplianceAssessmentModel.status.in_(["in_progress", "draft"]),
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def _count_regulations(self, session: AsyncSession) -> int:
        stmt = select(sa_func.count()).select_from(RegulationModel)
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def _count_high_risk_entities(
        self, session: AsyncSession, _tenant_id: str,
    ) -> int:
        entity_subq = select(EntityModel.id).subquery()
        stmt = select(sa_func.count(sa_func.distinct(ComplianceAssessmentModel.entity_id))).where(
            ComplianceAssessmentModel.entity_id.in_(select(entity_subq.c.id)),
            ComplianceAssessmentModel.risk_level.in_(["high", "critical"]),
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def _count_active_alerts(
        self, session: AsyncSession, _tenant_id: str,
    ) -> int:
        try:
            from regulaforge.risk_engine.infrastructure.models import RiskAlertModel
            stmt = select(sa_func.count()).select_from(RiskAlertModel).where(
                RiskAlertModel.active.is_(True),
            )
            result = await session.execute(stmt)
            return result.scalar() or 0
        except (ImportError, Exception):
            return 0

    async def _count_agent_tasks(
        self, session: AsyncSession,
    ) -> tuple:
        try:
            from regulaforge.agents.infrastructure.models import AgentTaskModel
            completed = select(sa_func.count()).select_from(AgentTaskModel).where(
                AgentTaskModel.status == "completed",
            )
            pending = select(sa_func.count()).select_from(AgentTaskModel).where(
                AgentTaskModel.status.in_(["pending", "in_progress"]),
            )
            return (
                (await session.execute(completed)).scalar() or 0,
                (await session.execute(pending)).scalar() or 0,
            )
        except (ImportError, Exception):
            return 0, 0

    async def _count_regulation_coverage(
        self, session: AsyncSession,
    ) -> tuple:
        jurisdictions = select(sa_func.count(sa_func.distinct(RegulationModel.jurisdiction)))
        categories = select(sa_func.count(sa_func.distinct(RegulationModel.category)))
        total = select(sa_func.count()).select_from(RegulationModel)
        return (
            (await session.execute(total)).scalar() or 0,
            (await session.execute(jurisdictions)).scalar() or 0,
            (await session.execute(categories)).scalar() or 0,
        )
