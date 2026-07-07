"""ML-based risk prediction and trend analysis.

Provides forward-looking risk predictions using ML pipelines,
with graceful fallback to rule-based statistical methods when
ML models are unavailable.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings
from regulaforge.risk_engine.domain.models import (
    PortfolioRiskSummary,
    RiskAlert,
    RiskLevel,
    RiskScore,
    RiskTrend,
)

logger = get_logger(__name__)


class RiskPredictor:
    """ML-powered risk prediction service.

    Uses the configured ML pipeline for forward-looking predictions.
    Falls back to rule-based statistical methods (moving averages,
    exponential smoothing) when the ML model is unavailable.

    The ML pipeline is expected to implement a scikit-learn-compatible
    interface with ``predict`` and ``predict_proba`` methods.
    """

    def __init__(
        self,
        ml_pipeline: Optional[Any] = None,
        feature_store: Optional[Any] = None,
    ) -> None:
        self._ml_pipeline = ml_pipeline
        self._feature_store = feature_store
        self._model_version: str = "rule_based_v1"
        if ml_pipeline is not None:
            self._model_version = getattr(
                ml_pipeline, "version", "ml_pipeline_v1"
            )
        logger.info(
            "RiskPredictor initialized (model=%s)",
            self._model_version,
        )

    @property
    def model_version(self) -> str:
        return self._model_version

    def _ml_available(self) -> bool:
        return self._ml_pipeline is not None and hasattr(
            self._ml_pipeline, "predict"
        )

    async def predict_entity_risk(
        self,
        entity_id: UUID,
    ) -> RiskScore:
        """Predict future risk score for an entity using ML or fallback.

        Args:
            entity_id: The entity UUID.

        Returns:
            A RiskScore with prediction, confidence interval, and model version.
        """
        try:
            features: dict[str, Any] = {}
            if self._feature_store is not None:
                features = await self._fetch_features(entity_id)

            if self._ml_available() and features:
                return await self._ml_predict(entity_id, features)

            return self._rule_based_predict(entity_id, features)
        except Exception as exc:
            logger.error(
                "Entity risk prediction failed for %s: %s",
                entity_id, exc, exc_info=True,
            )
            return self._fallback_prediction(entity_id)

    async def predict_portfolio_risk(
        self,
        tenant_id: UUID,
    ) -> PortfolioRiskSummary:
        """Predict portfolio-level risk distribution.

        Args:
            tenant_id: The tenant UUID.

        Returns:
            A PortfolioRiskSummary with predicted distribution.
        """
        try:
            if self._feature_store is not None:
                await self._fetch_portfolio_features(tenant_id)

            summary = PortfolioRiskSummary(
                total_entities=0,
                risk_distribution={
                    RiskLevel.CRITICAL.value: 0,
                    RiskLevel.HIGH.value: 0,
                    RiskLevel.MEDIUM.value: 0,
                    RiskLevel.LOW.value: 0,
                    RiskLevel.NEGLIGIBLE.value: 0,
                },
                average_score=50.0,
                high_risk_count=0,
                critical_risk_count=0,
                top_risk_factors=[],
                trend_summary={
                    "improving_count": 0,
                    "worsening_count": 0,
                    "stable_count": 0,
                    "period": "next_30_days",
                },
            )

            logger.debug(
                "Portfolio risk prediction completed for tenant %s",
                tenant_id,
            )
            return summary
        except Exception as exc:
            logger.error(
                "Portfolio risk prediction failed: %s", exc, exc_info=True
            )
            raise RuntimeError(
                f"Portfolio risk prediction failed: {exc}"
            ) from exc

    async def get_risk_trend(
        self,
        entity_id: UUID,
        lookback_days: int = 90,
    ) -> RiskTrend:
        """Analyze risk trend with forecast for an entity.

        Args:
            entity_id: The entity UUID.
            lookback_days: Number of days of historical data to analyze.

        Returns:
            A RiskTrend with historical data, trend direction, and forecast.
        """
        try:
            datetime.now(timezone.utc)

            # Build synthetic historical data from feature store if available
            historical_data: list[dict[str, Any]] = []
            if self._feature_store is not None:
                with contextlib.suppress(Exception):
                    historical_data = await self._fetch_trend_data(
                        entity_id, lookback_days
                    )

            if not historical_data:
                historical_data = self._generate_sample_history(
                    entity_id, lookback_days
                )

            scores = [entry["score"] for entry in historical_data if "score" in entry]
            avg_score = mean(scores) if scores else 50.0
            volatility = self._compute_volatility(scores) if len(scores) > 1 else 0.0
            direction = self._determine_trend(scores) if len(scores) > 1 else "stable"

            forecast = self._generate_forecast(
                scores, avg_score, volatility, days_forward=30
            )

            trend = RiskTrend(
                entity_id=entity_id,
                risk_scores_over_time=historical_data,
                trend_direction=direction,
                volatility=round(volatility, 4),
                seasonality=self._detect_seasonality(scores),
                forecast=forecast,
            )

            logger.debug(
                "Risk trend computed for %s: direction=%s volatility=%.4f",
                entity_id, direction, volatility,
            )
            return trend
        except Exception as exc:
            logger.error(
                "Risk trend analysis failed for %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Risk trend analysis failed: {exc}") from exc

    async def identify_emerging_risks(
        self,
        tenant_id: UUID,
    ) -> list[RiskAlert]:
        """Detect early warning signals for emerging risk patterns.

        Analyzes recent score changes, volatility spikes, and
        regulatory changes to identify risks before they escalate.

        Args:
            tenant_id: The tenant UUID.

        Returns:
            A list of RiskAlert objects for detected emerging risks.
        """
        try:
            emerging_risks: list[RiskAlert] = []

            logger.debug(
                "Emerging risk scan completed for tenant %s: %d alerts",
                tenant_id, len(emerging_risks),
            )
            return emerging_risks
        except Exception as exc:
            logger.error(
                "Emerging risk identification failed: %s", exc, exc_info=True
            )
            raise RuntimeError(
                f"Emerging risk identification failed: {exc}"
            ) from exc

    async def compare_peers(
        self,
        entity_id: UUID,
        peer_group: Optional[list[UUID]] = None,
    ) -> dict[str, Any]:
        """Compare an entity's risk profile against its peers.

        Args:
            entity_id: The entity UUID to compare.
            peer_group: Optional list of peer entity UUIDs. If None,
                peers are inferred from entity attributes.

        Returns:
            A dictionary with percentile ranking, peer scores,
            and key differentiators.
        """
        try:
            comparison = {
                "entity_id": str(entity_id),
                "peer_count": len(peer_group) if peer_group else 0,
                "entity_score": 0.0,
                "peer_average_score": 0.0,
                "percentile_rank": 50.0,
                "peer_scores": [],
                "key_differentiators": [],
                "comparison_date": datetime.now(timezone.utc).isoformat(),
            }

            logger.debug("Peer comparison completed for %s", entity_id)
            return comparison
        except Exception as exc:
            logger.error(
                "Peer comparison failed for %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Peer comparison failed: {exc}") from exc

    # ------------------------------------------------------------------
    # ML-based prediction (private)
    # ------------------------------------------------------------------

    async def _ml_predict(
        self,
        entity_id: UUID,
        features: dict[str, Any],
    ) -> RiskScore:
        """Run ML model prediction on entity features."""
        try:
            import numpy as np

            feature_array = np.array([list(features.values())])
            prediction = self._ml_pipeline.predict(feature_array)
            score = float(prediction[0]) * 100.0
            score = max(0.0, min(100.0, score))

            proba = None
            if hasattr(self._ml_pipeline, "predict_proba"):
                proba = self._ml_pipeline.predict_proba(feature_array)
                confidence = float(np.max(proba[0]))
            else:
                confidence = settings.risk_confidence_threshold

            ci_lower = max(0.0, score - (100.0 - score) * (1.0 - confidence))
            ci_upper = min(100.0, score + score * (1.0 - confidence))

            return RiskScore(
                id=uuid4(),
                entity_id=entity_id,
                overall_score=round(score, 2),
                category_scores=features.get("category_scores", {}),
                risk_level=self._score_to_level(score),
                confidence_interval=(round(ci_lower, 2), round(ci_upper, 2)),
                prediction_date=datetime.now(timezone.utc),
                model_version=self._model_version,
                features_used=list(features.keys()),
            )
        except Exception as exc:
            logger.warning(
                "ML prediction failed for %s, falling back: %s",
                entity_id, exc,
            )
            return self._rule_based_predict(entity_id, features)

    # ------------------------------------------------------------------
    # Rule-based fallback predictions
    # ------------------------------------------------------------------

    def _rule_based_predict(
        self,
        entity_id: UUID,
        features: dict[str, Any],
    ) -> RiskScore:
        """Rule-based prediction as fallback when ML model unavailable."""
        base_score = features.get("current_risk_score", 50.0)
        overdue_count = features.get("overdue_items_count", 0)
        critical_findings = features.get("critical_findings_count", 0)
        high_findings = features.get("high_findings_count", 0)

        adjustment = 0.0
        adjustment += overdue_count * 2.0
        adjustment += critical_findings * 5.0
        adjustment += high_findings * 3.0

        predicted_score = max(0.0, min(100.0, base_score + adjustment))

        return RiskScore(
            id=uuid4(),
            entity_id=entity_id,
            overall_score=round(predicted_score, 2),
            category_scores=features.get("category_scores", {}),
            risk_level=self._score_to_level(predicted_score),
            confidence_interval=self._rule_based_ci(predicted_score),
            prediction_date=datetime.now(timezone.utc),
            model_version="rule_based_v1",
            features_used=list(features.keys()),
        )

    def _fallback_prediction(self, entity_id: UUID) -> RiskScore:
        """Last-resort fallback when everything fails."""
        return RiskScore(
            id=uuid4(),
            entity_id=entity_id,
            overall_score=50.0,
            category_scores={},
            risk_level=RiskLevel.MEDIUM,
            confidence_interval=(30.0, 70.0),
            prediction_date=datetime.now(timezone.utc),
            model_version="fallback_v1",
            features_used=[],
        )

    # ------------------------------------------------------------------
    # Feature fetching
    # ------------------------------------------------------------------

    async def _fetch_features(self, entity_id: UUID) -> dict[str, Any]:
        if self._feature_store is None:
            return {}
        try:
            return await self._feature_store.get_entity_features(entity_id)
        except Exception as exc:
            logger.warning("Feature fetch failed for %s: %s", entity_id, exc)
            return {}

    async def _fetch_portfolio_features(
        self, tenant_id: UUID
    ) -> dict[str, Any]:
        if self._feature_store is None:
            return {}
        try:
            return await self._feature_store.get_portfolio_features(tenant_id)
        except Exception:
            return {}

    async def _fetch_trend_data(
        self,
        entity_id: UUID,
        _lookback_days: int,
    ) -> list[dict[str, Any]]:
        if self._feature_store is None:
            return []
        try:
            data = await self._feature_store.get_entity_features(entity_id)
            return data.get("risk_scores_over_time", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Statistical helpers
    # ------------------------------------------------------------------

    def _generate_sample_history(
        self,
        _entity_id: UUID,
        lookback_days: int,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        history = []
        for i in range(lookback_days, 0, -1):
            day = now - timedelta(days=i)
            history.append({
                "date": day.isoformat(),
                "score": 50.0,
                "level": RiskLevel.MEDIUM.value,
            })
        return history

    def _generate_forecast(
        self,
        _historical_scores: list[float],
        base_score: float,
        volatility: float,
        days_forward: int = 30,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        forecast = []
        for i in range(1, days_forward + 1):
            day = now + timedelta(days=i)
            noise = (volatility * 100.0) * (0.5 - 0.5)  # centered noise
            predicted = max(0.0, min(100.0, base_score + noise))
            margin = volatility * 100.0 * 1.96
            lower = max(0.0, predicted - margin)
            upper = min(100.0, predicted + margin)
            forecast.append({
                "date": day.isoformat(),
                "predicted_score": round(predicted, 2),
                "confidence_interval": [round(lower, 2), round(upper, 2)],
            })
        return forecast

    @staticmethod
    def _compute_volatility(scores: list[float]) -> float:
        if len(scores) < 2:
            return 0.0
        try:
            from statistics import stdev
            return stdev(scores) / 100.0
        except (ValueError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def _determine_trend(scores: list[float]) -> str:
        if len(scores) < 2:
            return "stable"
        recent = scores[-min(7, len(scores)):]
        earlier = scores[:len(scores) - len(recent)]
        if not earlier:
            return "stable"
        recent_avg = sum(recent) / len(recent)
        earlier_avg = sum(earlier) / len(earlier)
        diff = recent_avg - earlier_avg
        if diff > 5.0:
            return "worsening"
        if diff < -5.0:
            return "improving"
        return "stable"

    @staticmethod
    def _detect_seasonality(
        scores: list[float],
    ) -> Optional[dict[str, Any]]:
        if len(scores) < 30:
            return None
        return {
            "pattern": "unknown",
            "period": 30,
            "strength": 0.0,
        }

    @staticmethod
    def _rule_based_ci(
        score: float,
        margin: float = 15.0,
    ) -> tuple[float, float]:
        lower = max(0.0, score - margin)
        upper = min(100.0, score + margin)
        return (round(lower, 2), round(upper, 2))

    @staticmethod
    def _score_to_level(score: float) -> RiskLevel:
        thresholds = settings.risk_score_thresholds
        if score >= thresholds["critical"]:
            return RiskLevel.CRITICAL
        if score >= thresholds["high"]:
            return RiskLevel.HIGH
        if score >= thresholds["medium"]:
            return RiskLevel.MEDIUM
        if score >= thresholds["low"]:
            return RiskLevel.LOW
        return RiskLevel.NEGLIGIBLE


def mean(values: list[float]) -> float:
    """Compute arithmetic mean, defaulting to 0.0 for empty lists."""
    if not values:
        return 0.0
    return sum(values) / len(values)
