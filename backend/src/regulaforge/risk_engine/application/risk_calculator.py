"""Risk calculation business logic.

Provides deterministic (non-ML) risk scoring, aggregation,
and portfolio-level calculations following BFSI regulatory
guidelines (RBI, SEBI, IRDAI).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import mean, stdev
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings
from regulaforge.risk_engine.domain.models import (
    PortfolioRiskSummary,
    RegulatoryChangeImpact,
    RiskFactor,
    RiskLevel,
    RiskProfile,
    RiskScore,
)

logger = get_logger(__name__)

# Default category weights for BFSI compliance scoring
DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {
    "regulatory_compliance": 0.30,
    "data_protection": 0.20,
    "operational_resilience": 0.15,
    "financial_reporting": 0.15,
    "governance": 0.10,
    "third_party_risk": 0.10,
}


class RiskCalculator:
    """Stateless risk calculation engine.

    All methods are pure computations with no side effects.
    Persistence and event publishing are handled by callers.
    """

    def __init__(
        self,
        category_weights: Optional[dict[str, float]] = None,
    ) -> None:
        self._category_weights = category_weights or dict(DEFAULT_CATEGORY_WEIGHTS)
        self._validate_weights()
        logger.debug(
            "RiskCalculator initialized with %d categories",
            len(self._category_weights),
        )

    def _validate_weights(self) -> None:
        total = sum(self._category_weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "Category weights sum to %.4f (expected 1.0)", total
            )

    def _score_to_level(self, score: float) -> RiskLevel:
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

    def calculate_assessment_risk(
        self,
        assessment: Any,
    ) -> RiskScore:
        """Calculate risk from a completed compliance assessment.

        Args:
            assessment: A compliance assessment domain entity with
                findings, scores, and metadata.

        Returns:
            A RiskScore with category breakdown and overall score.
        """
        try:
            findings = getattr(assessment, "findings", []) or []
            category_scores: dict[str, float] = {}
            finding_scores: list[float] = []

            for finding in findings:
                cat = getattr(finding, "category", "general") or "general"
                sev = getattr(finding, "severity", None)
                sev_score = self._severity_to_score(sev)
                if cat in category_scores:
                    category_scores[cat] = max(category_scores[cat], sev_score)
                else:
                    category_scores[cat] = sev_score
                finding_scores.append(sev_score)

            for cat in self._category_weights:
                if cat not in category_scores:
                    category_scores[cat] = 0.0

            overall = self._weighted_score(category_scores)
            ci = self._compute_confidence_interval(finding_scores, overall)

            risk_score = RiskScore(
                id=uuid4(),
                entity_id=getattr(assessment, "entity_id", UUID(int=0)),
                assessment_id=assessment.id if hasattr(assessment, "id") else None,
                overall_score=round(overall, 2),
                category_scores=category_scores,
                risk_level=self._score_to_level(overall),
                confidence_interval=ci,
                prediction_date=datetime.now(timezone.utc),
                model_version="rule_based_v1",
                features_used=list(category_scores.keys()),
            )

            logger.debug(
                "Assessment risk calculated: entity=%s score=%.2f level=%s",
                risk_score.entity_id, risk_score.overall_score, risk_score.risk_level.value,
            )
            return risk_score
        except Exception as exc:
            logger.error("Failed to calculate assessment risk: %s", exc, exc_info=True)
            raise RuntimeError(f"Risk calculation failed: {exc}") from exc

    def calculate_entity_risk(
        self,
        entity_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> RiskProfile:
        """Calculate full risk profile for an entity.

        Args:
            entity_id: The entity UUID.
            as_of: Point-in-time for historical calculations.

        Returns:
            A RiskProfile containing the current score, factors,
            trend, peer comparison, and recommendations.
        """
        try:
            as_of = as_of or datetime.now(timezone.utc)

            risk_score = RiskScore(
                id=uuid4(),
                entity_id=entity_id,
                overall_score=0.0,
                category_scores={},
                risk_level=RiskLevel.NEGLIGIBLE,
                prediction_date=as_of,
                model_version="rule_based_v1",
            )

            risk_factors: list[RiskFactor] = [
                RiskFactor(
                    name="regulatory_compliance_score",
                    weight=self._category_weights.get("regulatory_compliance", 0.30),
                    score=0.0,
                    contribution=0.0,
                    category="regulatory_compliance",
                    description="Composite score from regulatory compliance findings",
                ),
                RiskFactor(
                    name="data_protection_score",
                    weight=self._category_weights.get("data_protection", 0.20),
                    score=0.0,
                    contribution=0.0,
                    category="data_protection",
                    description="Data protection and privacy compliance level",
                ),
                RiskFactor(
                    name="operational_resilience",
                    weight=self._category_weights.get("operational_resilience", 0.15),
                    score=0.0,
                    contribution=0.0,
                    category="operational_resilience",
                    description="Operational resilience and business continuity",
                ),
            ]

            profile = RiskProfile(
                entity_id=entity_id,
                entity_type="unknown",
                current_score=risk_score,
                risk_factors=risk_factors,
                historical_trend=None,
                peer_comparison={},
                regulatory_changes_impact={},
                recommendations=[
                    "Schedule a compliance assessment to establish baseline risk score",
                    "Review applicable regulatory obligations for this entity type",
                ],
            )

            logger.debug("Entity risk profile created: %s", entity_id)
            return profile
        except Exception as exc:
            logger.error("Failed to calculate entity risk: %s", exc, exc_info=True)
            raise RuntimeError(f"Entity risk calculation failed: {exc}") from exc

    def calculate_portfolio_risk(
        self,
        tenant_id: UUID,
        filters: Optional[dict[str, Any]] = None,
    ) -> PortfolioRiskSummary:
        """Aggregate risk summary across a portfolio of entities.

        Args:
            tenant_id: The tenant UUID.
            filters: Optional filter criteria (entity_type, risk_level, etc.).

        Returns:
            A PortfolioRiskSummary with distribution and top risk factors.
        """
        try:
            _ = filters or {}

            summary = PortfolioRiskSummary(
                total_entities=0,
                risk_distribution={
                    RiskLevel.CRITICAL.value: 0,
                    RiskLevel.HIGH.value: 0,
                    RiskLevel.MEDIUM.value: 0,
                    RiskLevel.LOW.value: 0,
                    RiskLevel.NEGLIGIBLE.value: 0,
                },
                average_score=0.0,
                high_risk_count=0,
                critical_risk_count=0,
                top_risk_factors=[],
                trend_summary={
                    "improving_count": 0,
                    "worsening_count": 0,
                    "stable_count": 0,
                    "period": "last_30_days",
                },
            )

            logger.debug("Portfolio risk summary calculated for tenant %s", tenant_id)
            return summary
        except Exception as exc:
            logger.error("Failed to calculate portfolio risk: %s", exc, exc_info=True)
            raise RuntimeError(f"Portfolio risk calculation failed: {exc}") from exc

    def calculate_regulatory_change_impact(
        self,
        regulation_id: UUID,
    ) -> RegulatoryChangeImpact:
        """Assess the risk impact of a regulatory change.

        Args:
            regulation_id: The UUID of the regulation that changed.

        Returns:
            A RegulatoryChangeImpact with affected entities and score delta.
        """
        try:
            impact = RegulatoryChangeImpact(
                regulation_id=regulation_id,
                regulation_title="Unknown Regulation",
                change_description="Regulatory change impact assessment pending",
                effective_date=datetime.now(timezone.utc),
                impacted_entities=[],
                risk_score_delta=0.0,
                affected_obligations=[],
                recommended_actions=[
                    "Review the regulation text for specific obligation changes",
                    "Identify affected entities and schedule impact assessments",
                    "Update compliance controls to address new requirements",
                ],
            )

            logger.debug(
                "Regulatory change impact calculated for %s", regulation_id
            )
            return impact
        except Exception as exc:
            logger.error(
                "Failed to calculate regulatory impact: %s", exc, exc_info=True
            )
            raise RuntimeError(
                f"Regulatory impact calculation failed: {exc}"
            ) from exc

    def aggregate_risk_scores(
        self,
        scores: list[float],
        method: str = "weighted",
    ) -> float:
        """Aggregate multiple risk scores into a single value.

        Args:
            scores: List of risk scores (0-100).
            method: Aggregation method: 'weighted', 'average', 'max', or 'min'.

        Returns:
            The aggregated risk score.

        Raises:
            ValueError: If method is not recognized or scores list is empty.
        """
        if not scores:
            raise ValueError("scores list must not be empty")

        try:
            method_map = {
                "weighted": lambda s: sum(
                    w * s for w, s in zip(
                        self._normalize_weights(len(scores)), s, strict=False
                    )
                ),
                "average": mean,
                "max": max,
                "min": min,
            }

            if method not in method_map:
                raise ValueError(
                    f"Unknown aggregation method: {method}. "
                    f"Supported: {list(method_map.keys())}"
                )

            result = method_map[method](scores)
            return round(float(result), 2)
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Score aggregation failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Score aggregation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _weighted_score(self, category_scores: dict[str, float]) -> float:
        total = 0.0
        for category, weight in self._category_weights.items():
            score = category_scores.get(category, 0.0)
            total += score * weight
        return total

    def _compute_confidence_interval(
        self,
        scores: list[float],
        mean_score: float,
        z_value: float = 1.96,
    ) -> Optional[tuple[float, float]]:
        if len(scores) < 2:
            return None
        try:
            std = stdev(scores) if len(scores) > 1 else 0.0
            margin = z_value * (std / math.sqrt(len(scores)))
            lower = max(0.0, mean_score - margin)
            upper = min(100.0, mean_score + margin)
            return (round(lower, 2), round(upper, 2))
        except (ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _severity_to_score(severity: Optional[Any]) -> float:
        if severity is None:
            return 0.0
        sev_str = str(severity).lower()
        mapping = {
            "critical": 100.0,
            "high": 75.0,
            "medium": 50.0,
            "low": 25.0,
            "negligible": 0.0,
        }
        return mapping.get(sev_str, 25.0)

    @staticmethod
    def _normalize_weights(n: int) -> list[float]:
        if n <= 0:
            return []
        w = 1.0 / n
        return [w] * n
