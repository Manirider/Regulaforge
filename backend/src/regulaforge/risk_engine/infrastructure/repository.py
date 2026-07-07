"""SQLAlchemy-based repositories for Risk Engine persistence.

Implements data access for risk scores, alerts, and trend data
following the same patterns as the audit infrastructure repository.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.config.logging import get_logger
from regulaforge.risk_engine.domain.models import RiskAlert, RiskLevel, RiskScore
from regulaforge.risk_engine.infrastructure.models import RiskAlertModel, RiskScoreModel

logger = get_logger(__name__)


class SqlAlchemyRiskScoreRepository:
    """Repository for persisting and querying RiskScore objects.

    Provides CRUD operations, search, and trend data retrieval
    using SQLAlchemy async sessions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, risk_score: RiskScore) -> RiskScore:
        """Persist a risk score.

        Args:
            risk_score: The RiskScore to persist.

        Returns:
            The saved RiskScore.

        Raises:
            RuntimeError: If persistence fails.
        """
        try:
            ci_lower = None
            ci_upper = None
            if risk_score.confidence_interval is not None:
                ci_lower, ci_upper = risk_score.confidence_interval

            model = RiskScoreModel(
                id=risk_score.id,
                entity_id=risk_score.entity_id,
                assessment_id=risk_score.assessment_id,
                overall_score=risk_score.overall_score,
                category_scores=risk_score.category_scores,
                risk_level=risk_score.risk_level.value,
                confidence_lower=ci_lower,
                confidence_upper=ci_upper,
                prediction_date=risk_score.prediction_date,
                model_version=risk_score.model_version,
                features_used=risk_score.features_used,
            )
            self._session.add(model)
            await self._session.flush()
            logger.debug(
                "Risk score saved: entity=%s score=%.2f level=%s",
                risk_score.entity_id, risk_score.overall_score, risk_score.risk_level.value,
            )
            return risk_score
        except Exception as exc:
            logger.error("Failed to save risk score: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to save risk score: {exc}") from exc

    async def get_by_id(self, score_id: UUID) -> Optional[RiskScore]:
        """Retrieve a risk score by its UUID.

        Args:
            score_id: The risk score UUID.

        Returns:
            The RiskScore if found, None otherwise.
        """
        try:
            query = select(RiskScoreModel).where(RiskScoreModel.id == score_id)
            result = await self._session.execute(query)
            model = result.scalar_one_or_none()
            return self._model_to_domain(model) if model else None
        except Exception as exc:
            logger.error("Failed to get risk score %s: %s", score_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to get risk score: {exc}") from exc

    async def get_by_entity(
        self,
        entity_id: UUID,
        limit: int = 10,
    ) -> list[RiskScore]:
        """Get recent risk scores for an entity.

        Args:
            entity_id: The entity UUID.
            limit: Maximum number of scores to return.

        Returns:
            List of RiskScore objects ordered by prediction_date DESC.
        """
        try:
            query = (
                select(RiskScoreModel)
                .where(RiskScoreModel.entity_id == entity_id)
                .order_by(RiskScoreModel.prediction_date.desc())
                .limit(limit)
            )
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]
        except Exception as exc:
            logger.error(
                "Failed to get risk scores for entity %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to get entity risk scores: {exc}") from exc

    async def get_recent(
        self,
        entity_id: UUID,
        since: Optional[datetime] = None,
    ) -> list[RiskScore]:
        """Get risk scores since a given date for an entity.

        Args:
            entity_id: The entity UUID.
            since: Start date (inclusive). Defaults to 30 days ago.

        Returns:
            List of RiskScore objects.
        """
        if since is None:
            since = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=30)
        try:
            query = (
                select(RiskScoreModel)
                .where(
                    and_(
                        RiskScoreModel.entity_id == entity_id,
                        RiskScoreModel.prediction_date >= since,
                    )
                )
                .order_by(RiskScoreModel.prediction_date.asc())
            )
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]
        except Exception as exc:
            logger.error(
                "Failed to get recent scores for entity %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to get recent scores: {exc}") from exc

    async def get_trend_data(
        self,
        entity_id: UUID,
        days: int = 90,
    ) -> list[dict[str, Any]]:
        """Get trend data points for an entity over a period.

        Args:
            entity_id: The entity UUID.
            days: Number of days of history.

        Returns:
            List of dicts with date, score, and level keys.
        """
        since = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)
        try:
            query = (
                select(
                    RiskScoreModel.prediction_date,
                    RiskScoreModel.overall_score,
                    RiskScoreModel.risk_level,
                )
                .where(
                    and_(
                        RiskScoreModel.entity_id == entity_id,
                        RiskScoreModel.prediction_date >= since,
                    )
                )
                .order_by(RiskScoreModel.prediction_date.asc())
            )
            result = await self._session.execute(query)
            rows = result.all()
            return [
                {
                    "date": row.prediction_date.isoformat(),
                    "score": row.overall_score,
                    "level": row.risk_level,
                }
                for row in rows
            ]
        except Exception as exc:
            logger.error(
                "Failed to get trend data for entity %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to get trend data: {exc}") from exc

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RiskScore], int]:
        """Search risk scores with filtering and pagination.

        Args:
            filters: Dictionary of filter criteria.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (risk scores list, total count).
        """
        try:
            query = self._build_search_query(filters or {})
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self._session.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            paginated_query = query.order_by(
                RiskScoreModel.prediction_date.desc()
            ).offset(offset).limit(page_size)
            result = await self._session.execute(paginated_query)
            models = result.scalars().all()

            return [self._model_to_domain(m) for m in models], total_count
        except Exception as exc:
            logger.error("Failed to search risk scores: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to search risk scores: {exc}") from exc

    def _build_search_query(self, filters: dict[str, Any]) -> Select:
        conditions = []
        entity_id = filters.get("entity_id")
        if entity_id is not None:
            conditions.append(RiskScoreModel.entity_id == entity_id)
        risk_level = filters.get("risk_level")
        if risk_level is not None:
            if isinstance(risk_level, RiskLevel):
                conditions.append(RiskScoreModel.risk_level == risk_level.value)
            else:
                conditions.append(RiskScoreModel.risk_level == str(risk_level))
        assessment_id = filters.get("assessment_id")
        if assessment_id is not None:
            conditions.append(RiskScoreModel.assessment_id == assessment_id)
        min_score = filters.get("min_score")
        if min_score is not None:
            conditions.append(RiskScoreModel.overall_score >= min_score)
        max_score = filters.get("max_score")
        if max_score is not None:
            conditions.append(RiskScoreModel.overall_score <= max_score)
        start_date = filters.get("start_date")
        if start_date is not None:
            conditions.append(RiskScoreModel.prediction_date >= start_date)
        end_date = filters.get("end_date")
        if end_date is not None:
            conditions.append(RiskScoreModel.prediction_date < end_date)
        model_version = filters.get("model_version")
        if model_version is not None:
            conditions.append(RiskScoreModel.model_version == model_version)
        return select(RiskScoreModel).where(and_(*conditions)) if conditions else select(RiskScoreModel)

    @staticmethod
    def _model_to_domain(model: RiskScoreModel) -> RiskScore:
        ci = None
        if model.confidence_lower is not None and model.confidence_upper is not None:
            ci = (model.confidence_lower, model.confidence_upper)
        return RiskScore(
            id=model.id,
            entity_id=model.entity_id,
            assessment_id=model.assessment_id,
            overall_score=model.overall_score,
            category_scores=model.category_scores or {},
            risk_level=RiskLevel(model.risk_level),
            confidence_interval=ci,
            prediction_date=model.prediction_date,
            model_version=model.model_version,
            features_used=model.features_used or [],
        )


class SqlAlchemyRiskAlertRepository:
    """Repository for persisting and querying RiskAlert objects."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, alert: RiskAlert) -> RiskAlert:
        """Persist a risk alert.

        Args:
            alert: The RiskAlert to persist.

        Returns:
            The saved RiskAlert.
        """
        try:
            model = RiskAlertModel(
                id=alert.id,
                entity_id=alert.entity_id,
                alert_type=alert.alert_type,
                severity=alert.severity.value,
                message=alert.message,
                details=alert.details,
                triggered_at=alert.triggered_at,
                acknowledged_at=alert.acknowledged_at,
                acknowledged_by=alert.acknowledged_by,
                resolved_at=alert.resolved_at,
            )
            self._session.add(model)
            await self._session.flush()
            logger.debug(
                "Alert saved: entity=%s type=%s severity=%s",
                alert.entity_id, alert.alert_type, alert.severity.value,
            )
            return alert
        except Exception as exc:
            logger.error("Failed to save alert: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to save alert: {exc}") from exc

    async def get_by_id(self, alert_id: UUID) -> Optional[RiskAlert]:
        """Retrieve an alert by its UUID."""
        try:
            query = select(RiskAlertModel).where(RiskAlertModel.id == alert_id)
            result = await self._session.execute(query)
            model = result.scalar_one_or_none()
            return self._model_to_domain(model) if model else None
        except Exception as exc:
            logger.error("Failed to get alert %s: %s", alert_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to get alert: {exc}") from exc

    async def get_by_entity(
        self,
        entity_id: UUID,
        limit: int = 50,
    ) -> list[RiskAlert]:
        """Get alerts for an entity, most recent first."""
        try:
            query = (
                select(RiskAlertModel)
                .where(RiskAlertModel.entity_id == entity_id)
                .order_by(RiskAlertModel.triggered_at.desc())
                .limit(limit)
            )
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]
        except Exception as exc:
            logger.error(
                "Failed to get alerts for entity %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to get entity alerts: {exc}") from exc

    async def get_by_entity_since(
        self,
        entity_id: UUID,
        since: datetime,
    ) -> list[RiskAlert]:
        """Get alerts for an entity triggered since a given date."""
        try:
            query = (
                select(RiskAlertModel)
                .where(
                    and_(
                        RiskAlertModel.entity_id == entity_id,
                        RiskAlertModel.triggered_at >= since,
                    )
                )
                .order_by(RiskAlertModel.triggered_at.desc())
            )
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]
        except Exception as exc:
            logger.error(
                "Failed to get alert history for %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to get alert history: {exc}") from exc

    async def get_active(
        self,
        entity_id: Optional[UUID] = None,
    ) -> list[RiskAlert]:
        """Get all active (unresolved) alerts, optionally filtered by entity."""
        try:
            conditions = [RiskAlertModel.resolved_at.is_(None)]
            if entity_id is not None:
                conditions.append(RiskAlertModel.entity_id == entity_id)
            query = (
                select(RiskAlertModel)
                .where(and_(*conditions))
                .order_by(RiskAlertModel.severity.desc(), RiskAlertModel.triggered_at.desc())
            )
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_domain(m) for m in models]
        except Exception as exc:
            logger.error("Failed to get active alerts: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to get active alerts: {exc}") from exc

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RiskAlert], int]:
        """Search alerts with filtering and pagination."""
        try:
            query = self._build_search_query(filters or {})
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self._session.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            paginated_query = query.order_by(
                RiskAlertModel.triggered_at.desc()
            ).offset(offset).limit(page_size)
            result = await self._session.execute(paginated_query)
            models = result.scalars().all()

            return [self._model_to_domain(m) for m in models], total_count
        except Exception as exc:
            logger.error("Failed to search alerts: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to search alerts: {exc}") from exc

    def _build_search_query(self, filters: dict[str, Any]) -> Select:
        conditions = []
        entity_id = filters.get("entity_id")
        if entity_id is not None:
            conditions.append(RiskAlertModel.entity_id == entity_id)
        alert_type = filters.get("alert_type")
        if alert_type is not None:
            conditions.append(RiskAlertModel.alert_type == alert_type)
        severity = filters.get("severity")
        if severity is not None:
            if isinstance(severity, RiskLevel):
                conditions.append(RiskAlertModel.severity == severity.value)
            else:
                conditions.append(RiskAlertModel.severity == str(severity))
        is_active = filters.get("is_active")
        if is_active is not None:
            if is_active:
                conditions.append(RiskAlertModel.resolved_at.is_(None))
            else:
                conditions.append(RiskAlertModel.resolved_at.isnot(None))
        start_date = filters.get("start_date")
        if start_date is not None:
            conditions.append(RiskAlertModel.triggered_at >= start_date)
        end_date = filters.get("end_date")
        if end_date is not None:
            conditions.append(RiskAlertModel.triggered_at < end_date)
        return select(RiskAlertModel).where(and_(*conditions)) if conditions else select(RiskAlertModel)

    @staticmethod
    def _model_to_domain(model: RiskAlertModel) -> RiskAlert:
        return RiskAlert(
            id=model.id,
            entity_id=model.entity_id,
            alert_type=model.alert_type,
            severity=RiskLevel(model.severity),
            message=model.message,
            details=model.details or {},
            triggered_at=model.triggered_at,
            acknowledged_at=model.acknowledged_at,
            acknowledged_by=model.acknowledged_by,
            resolved_at=model.resolved_at,
        )
