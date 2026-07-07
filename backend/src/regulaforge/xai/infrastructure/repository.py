"""SQLAlchemy-based repository for XAI explanations.

Provides CRUD operations for persisting and querying explanations
and counterfactuals using async SQLAlchemy sessions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.config.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from regulaforge.config.logging import get_logger
from regulaforge.xai.domain.models import (
    CounterfactualExplanation,
    Explanation,
    ExplanationType,
    FeatureContribution,
)
from regulaforge.xai.infrastructure.models import (
    CounterfactualModel,
    ExplanationModel,
)

logger = get_logger(__name__)


class SqlAlchemyExplanationRepository:
    """SQLAlchemy implementation of explanation repository.

    Provides async persistence for explanations and counterfactuals
    with comprehensive querying, pagination, and cleanup capabilities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, explanation: Explanation) -> Explanation:
        """Persist an explanation to the database.

        Args:
            explanation: The Explanation domain entity to save.

        Returns:
            The saved Explanation.

        Raises:
            RuntimeError: If database persistence fails.
        """
        try:
            existing = await self._session.get(ExplanationModel, explanation.id)
            if existing:
                self._update_model(existing, explanation)
            else:
                model = self._to_model(explanation)
                self._session.add(model)

            await self._session.flush()
            logger.debug("Explanation saved: id=%s type=%s", explanation.id, explanation.explanation_type.value)
            return explanation
        except Exception as exc:
            logger.error("Failed to save explanation %s: %s", explanation.id, exc, exc_info=True)
            raise RuntimeError(f"Failed to save explanation: {exc}") from exc

    async def get_by_id(self, explanation_id: UUID) -> Optional[Explanation]:
        """Retrieve an explanation by its UUID.

        Args:
            explanation_id: UUID of the explanation.

        Returns:
            Explanation if found, None otherwise.
        """
        try:
            model = await self._session.get(ExplanationModel, explanation_id)
            if model is None:
                return None
            return self._to_domain(model)
        except Exception as exc:
            logger.error("Failed to get explanation %s: %s", explanation_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to get explanation: {exc}") from exc

    async def get_by_prediction(
        self,
        prediction_id: UUID,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Explanation], int]:
        """Get all explanations for a given prediction.

        Args:
            prediction_id: UUID of the prediction.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of Explanations, total count).
        """
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

        try:
            query = (
                select(ExplanationModel)
                .where(ExplanationModel.prediction_id == prediction_id)
                .order_by(ExplanationModel.explanation_timestamp.desc())
            )
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self._session.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            paginated = query.offset(offset).limit(page_size)
            result = await self._session.execute(paginated)
            models = result.scalars().all()

            explanations = [self._to_domain(m) for m in models]
            logger.debug("Retrieved %d explanations for prediction %s", len(explanations), prediction_id)
            return explanations, total_count
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to get explanations for prediction %s: %s", prediction_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to get explanations: {exc}") from exc

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Explanation], int]:
        """Search explanations with optional filters.

        Supported filters:
            - model_name: str
            - explanation_type: str
            - confidence_min: float
            - confidence_max: float
            - created_after: datetime
            - created_before: datetime

        Args:
            filters: Dict of filter criteria.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of Explanations, total count).
        """
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

        try:
            query = self._build_search_query(filters or {})
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self._session.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            paginated = (
                query.order_by(ExplanationModel.explanation_timestamp.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await self._session.execute(paginated)
            models = result.scalars().all()

            explanations = [self._to_domain(m) for m in models]
            logger.debug("Search returned %d of %d explanations", len(explanations), total_count)
            return explanations, total_count
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to search explanations: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to search explanations: {exc}") from exc

    async def delete_old(self, before: Optional[datetime] = None) -> int:
        """Delete explanations older than the specified date.

        Args:
            before: Cutoff datetime. Defaults to 90 days ago.

        Returns:
            Number of deleted records.
        """
        if before is None:
            before = datetime.now(timezone.utc) - timedelta(days=90)

        try:
            query = select(ExplanationModel).where(
                ExplanationModel.explanation_timestamp < before
            )
            result = await self._session.execute(query)
            models = result.scalars().all()

            count = len(models)
            for model in models:
                await self._session.delete(model)

            await self._session.flush()
            logger.info("Deleted %d explanations older than %s", count, before.isoformat())
            return count
        except Exception as exc:
            logger.error("Failed to delete old explanations: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to delete old explanations: {exc}") from exc

    async def save_counterfactual(
        self,
        counterfactual: CounterfactualExplanation,
    ) -> CounterfactualExplanation:
        """Persist a counterfactual explanation.

        Args:
            counterfactual: The CounterfactualExplanation to save.

        Returns:
            The saved CounterfactualExplanation.
        """
        try:
            existing = await self._session.get(CounterfactualModel, counterfactual.id)
            if existing:
                self._update_cf_model(existing, counterfactual)
            else:
                model = self._cf_to_model(counterfactual)
                self._session.add(model)

            await self._session.flush()
            logger.debug("Counterfactual saved: id=%s", counterfactual.id)
            return counterfactual
        except Exception as exc:
            logger.error("Failed to save counterfactual %s: %s", counterfactual.id, exc, exc_info=True)
            raise RuntimeError(f"Failed to save counterfactual: {exc}") from exc

    def _build_search_query(self, filters: dict[str, Any]) -> Any:
        """Build a SQLAlchemy select query from filters."""
        conditions = []

        model_name = filters.get("model_name")
        if model_name is not None:
            conditions.append(ExplanationModel.model_name == str(model_name))

        explanation_type = filters.get("explanation_type")
        if explanation_type is not None:
            conditions.append(ExplanationModel.explanation_type == str(explanation_type))

        confidence_min = filters.get("confidence_min")
        if confidence_min is not None:
            conditions.append(ExplanationModel.confidence >= float(confidence_min))

        confidence_max = filters.get("confidence_max")
        if confidence_max is not None:
            conditions.append(ExplanationModel.confidence <= float(confidence_max))

        created_after = filters.get("created_after")
        if created_after is not None:
            conditions.append(ExplanationModel.explanation_timestamp >= created_after)

        created_before = filters.get("created_before")
        if created_before is not None:
            conditions.append(ExplanationModel.explanation_timestamp <= created_before)

        prediction_id = filters.get("prediction_id")
        if prediction_id is not None:
            if isinstance(prediction_id, UUID):
                conditions.append(ExplanationModel.prediction_id == prediction_id)
            else:
                conditions.append(ExplanationModel.prediction_id == UUID(str(prediction_id)))

        base_query = select(ExplanationModel)
        if conditions:
            return base_query.where(and_(*conditions))
        return base_query

    @staticmethod
    def _to_model(explanation: Explanation) -> ExplanationModel:
        """Convert domain Explanation to ORM model."""
        return ExplanationModel(
            id=explanation.id,
            prediction_id=explanation.prediction_id,
            model_name=explanation.model_name,
            explanation_type=explanation.explanation_type.value,
            features=[f.to_dict() for f in explanation.features],
            summary=explanation.summary,
            confidence=explanation.confidence,
            visualization_data=dict(explanation.visualization_data),
            metadata_json=dict(explanation.metadata),
            explanation_timestamp=explanation.timestamp,
        )

    @staticmethod
    def _to_domain(model: ExplanationModel) -> Explanation:
        """Convert ORM model to domain Explanation."""
        features_data = model.features or []
        features = [
            FeatureContribution.from_dict(fd) if isinstance(fd, dict) else fd
            for fd in features_data
        ]
        return Explanation(
            id=model.id,
            prediction_id=model.prediction_id,
            model_name=model.model_name,
            explanation_type=ExplanationType(model.explanation_type),
            features=features,
            summary=model.summary or "",
            confidence=model.confidence,
            visualization_data=dict(model.visualization_data or {}),
            timestamp=model.explanation_timestamp,
            metadata=dict(model.metadata_json or {}),
        )

    @staticmethod
    def _update_model(model: ExplanationModel, explanation: Explanation) -> None:
        """Update an existing ORM model with domain data."""
        model.prediction_id = explanation.prediction_id
        model.model_name = explanation.model_name
        model.explanation_type = explanation.explanation_type.value
        model.features = [f.to_dict() for f in explanation.features]
        model.summary = explanation.summary
        model.confidence = explanation.confidence
        model.visualization_data = dict(explanation.visualization_data)
        model.metadata_json = dict(explanation.metadata)
        model.explanation_timestamp = explanation.timestamp

    @staticmethod
    def _cf_to_model(cf: CounterfactualExplanation) -> CounterfactualModel:
        """Convert domain CounterfactualExplanation to ORM model."""
        return CounterfactualModel(
            id=cf.id,
            prediction_id=UUID(int=0),
            original_input=dict(cf.original_input),
            counterfactual_input=dict(cf.counterfactual_input),
            feature_changes=list(cf.feature_changes),
            outcome_change=cf.outcome_change,
            distance=cf.distance,
            viability=cf.viability,
            natural_language=cf.natural_language,
        )

    @staticmethod
    def _update_cf_model(model: CounterfactualModel, cf: CounterfactualExplanation) -> None:
        """Update an existing CounterfactualModel with domain data."""
        model.original_input = dict(cf.original_input)
        model.counterfactual_input = dict(cf.counterfactual_input)
        model.feature_changes = list(cf.feature_changes)
        model.outcome_change = cf.outcome_change
        model.distance = cf.distance
        model.viability = cf.viability
        model.natural_language = cf.natural_language
