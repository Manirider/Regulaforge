"""Pure domain models for the Risk Prediction Engine.

These are plain Python dataclasses with validation — no ORM
dependencies. Follows the same pattern as the Knowledge Graph
domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class RiskLevel(str, Enum):
    """Risk severity classification aligned with BFSI regulatory standards."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


@dataclass
class RiskScore:
    """A risk score computed for an entity or assessment.

    Includes overall score, per-category breakdown, confidence
    interval, and model metadata for traceability.
    """

    id: UUID
    entity_id: UUID
    assessment_id: Optional[UUID] = None
    overall_score: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.NEGLIGIBLE
    confidence_interval: Optional[tuple[float, float]] = None
    prediction_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = "rule_based_v1"
    features_used: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("id must be a UUID")
        if not isinstance(self.entity_id, UUID):
            raise ValueError("entity_id must be a UUID")
        if self.assessment_id is not None and not isinstance(self.assessment_id, UUID):
            raise ValueError("assessment_id must be a UUID or None")
        if not isinstance(self.overall_score, int | float):
            raise ValueError("overall_score must be numeric")
        if self.overall_score < 0.0 or self.overall_score > 100.0:
            raise ValueError("overall_score must be between 0 and 100")
        if not isinstance(self.category_scores, dict):
            raise ValueError("category_scores must be a dict")
        for key, val in self.category_scores.items():
            if not isinstance(val, int | float) or val < 0.0 or val > 100.0:
                raise ValueError(f"category_scores[{key!r}] must be a float between 0 and 100")
        if not isinstance(self.risk_level, RiskLevel):
            raise ValueError("risk_level must be a RiskLevel enum")
        if self.confidence_interval is not None:
            if not isinstance(self.confidence_interval, tuple) or len(self.confidence_interval) != 2:
                raise ValueError("confidence_interval must be a tuple of (lower, upper) or None")
            lower, upper = self.confidence_interval
            if not isinstance(lower, int | float) or not isinstance(upper, int | float):
                raise ValueError("confidence_interval values must be numeric")
            if lower < 0.0 or upper > 100.0 or lower > upper:
                raise ValueError("confidence_interval must satisfy 0 <= lower <= upper <= 100")
        if not isinstance(self.prediction_date, datetime):
            raise ValueError("prediction_date must be a datetime")
        if not self.model_version or not isinstance(self.model_version, str):
            raise ValueError("model_version must be a non-empty string")
        if not isinstance(self.features_used, list):
            raise ValueError("features_used must be a list")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "entity_id": str(self.entity_id),
            "assessment_id": str(self.assessment_id) if self.assessment_id else None,
            "overall_score": self.overall_score,
            "category_scores": dict(self.category_scores),
            "risk_level": self.risk_level.value,
            "confidence_interval": list(self.confidence_interval) if self.confidence_interval else None,
            "prediction_date": self.prediction_date.isoformat(),
            "model_version": self.model_version,
            "features_used": list(self.features_used),
        }


@dataclass
class RiskFactor:
    """A single risk factor contributing to a risk score.

    Each factor carries a SHAP-based contribution value for
    explainability, along with its category and description.
    """

    name: str
    weight: float = 1.0
    score: float = 0.0
    contribution: float = 0.0
    category: str = "general"
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.weight, int | float) or self.weight < 0.0:
            raise ValueError("weight must be a non-negative number")
        if not isinstance(self.score, int | float) or self.score < 0.0 or self.score > 100.0:
            raise ValueError("score must be between 0 and 100")
        if not isinstance(self.contribution, int | float):
            raise ValueError("contribution must be numeric")
        if not self.category or not isinstance(self.category, str):
            raise ValueError("category must be a non-empty string")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": self.score,
            "contribution": self.contribution,
            "category": self.category,
            "description": self.description,
        }


@dataclass
class RiskTrend:
    """Historical risk trend with forecast for an entity.

    Supports trend direction analysis, volatility measurement,
    seasonal pattern detection, and forward-looking forecasts.
    """

    entity_id: UUID
    risk_scores_over_time: list[dict[str, Any]] = field(default_factory=list)
    trend_direction: str = "stable"
    volatility: float = 0.0
    seasonality: Optional[dict[str, Any]] = None
    forecast: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, UUID):
            raise ValueError("entity_id must be a UUID")
        if not isinstance(self.risk_scores_over_time, list):
            raise ValueError("risk_scores_over_time must be a list")
        for entry in self.risk_scores_over_time:
            if not isinstance(entry, dict):
                raise ValueError("each entry in risk_scores_over_time must be a dict")
            if "date" not in entry or "score" not in entry:
                raise ValueError("each entry must have 'date' and 'score' keys")
        valid_directions = {"improving", "worsening", "stable"}
        if self.trend_direction not in valid_directions:
            raise ValueError(f"trend_direction must be one of {valid_directions}")
        if not isinstance(self.volatility, int | float) or self.volatility < 0.0:
            raise ValueError("volatility must be a non-negative number")
        if self.seasonality is not None and not isinstance(self.seasonality, dict):
            raise ValueError("seasonality must be a dict or None")
        if not isinstance(self.forecast, list):
            raise ValueError("forecast must be a list")
        for entry in self.forecast:
            if not isinstance(entry, dict):
                raise ValueError("each entry in forecast must be a dict")
            if "date" not in entry or "predicted_score" not in entry:
                raise ValueError("each forecast entry must have 'date' and 'predicted_score' keys")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": str(self.entity_id),
            "risk_scores_over_time": list(self.risk_scores_over_time),
            "trend_direction": self.trend_direction,
            "volatility": self.volatility,
            "seasonality": dict(self.seasonality) if self.seasonality else None,
            "forecast": list(self.forecast),
        }


@dataclass
class RiskAlert:
    """An alert generated when a risk threshold is breached or a pattern is detected."""

    id: UUID
    entity_id: UUID
    alert_type: str
    severity: RiskLevel
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("id must be a UUID")
        if not isinstance(self.entity_id, UUID):
            raise ValueError("entity_id must be a UUID")
        if not self.alert_type or not isinstance(self.alert_type, str):
            raise ValueError("alert_type must be a non-empty string")
        if not isinstance(self.severity, RiskLevel):
            raise ValueError("severity must be a RiskLevel enum")
        if not self.message or not isinstance(self.message, str):
            raise ValueError("message must be a non-empty string")
        if not isinstance(self.details, dict):
            raise ValueError("details must be a dict")
        if not isinstance(self.triggered_at, datetime):
            raise ValueError("triggered_at must be a datetime")
        if self.acknowledged_at is not None and not isinstance(self.acknowledged_at, datetime):
            raise ValueError("acknowledged_at must be a datetime or None")
        if self.acknowledged_by is not None and not isinstance(self.acknowledged_by, UUID):
            raise ValueError("acknowledged_by must be a UUID or None")
        if self.resolved_at is not None and not isinstance(self.resolved_at, datetime):
            raise ValueError("resolved_at must be a datetime or None")

    @property
    def is_active(self) -> bool:
        return self.resolved_at is None

    @property
    def is_acknowledged(self) -> bool:
        return self.acknowledged_at is not None

    def acknowledge(self, user_id: UUID) -> None:
        self.acknowledged_at = datetime.now(timezone.utc)
        self.acknowledged_by = user_id

    def resolve(self) -> None:
        self.resolved_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "entity_id": str(self.entity_id),
            "alert_type": self.alert_type,
            "severity": self.severity.value,
            "message": self.message,
            "details": dict(self.details),
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": str(self.acknowledged_by) if self.acknowledged_by else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "is_active": self.is_active,
            "is_acknowledged": self.is_acknowledged,
        }


@dataclass
class RiskProfile:
    """Full risk profile for an entity.

    Aggregates the current risk score, contributing factors,
    historical trends, peer comparison, and regulatory change
    impact assessment.
    """

    entity_id: UUID
    entity_type: str
    current_score: RiskScore
    risk_factors: list[RiskFactor] = field(default_factory=list)
    historical_trend: Optional[RiskTrend] = None
    peer_comparison: dict[str, Any] = field(default_factory=dict)
    regulatory_changes_impact: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, UUID):
            raise ValueError("entity_id must be a UUID")
        if not self.entity_type or not isinstance(self.entity_type, str):
            raise ValueError("entity_type must be a non-empty string")
        if not isinstance(self.current_score, RiskScore):
            raise ValueError("current_score must be a RiskScore instance")
        if not isinstance(self.risk_factors, list):
            raise ValueError("risk_factors must be a list")
        if self.historical_trend is not None and not isinstance(self.historical_trend, RiskTrend):
            raise ValueError("historical_trend must be a RiskTrend or None")
        if not isinstance(self.peer_comparison, dict):
            raise ValueError("peer_comparison must be a dict")
        if not isinstance(self.regulatory_changes_impact, dict):
            raise ValueError("regulatory_changes_impact must be a dict")
        if not isinstance(self.recommendations, list):
            raise ValueError("recommendations must be a list")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": str(self.entity_id),
            "entity_type": self.entity_type,
            "current_score": self.current_score.to_dict(),
            "risk_factors": [f.to_dict() for f in self.risk_factors],
            "historical_trend": self.historical_trend.to_dict() if self.historical_trend else None,
            "peer_comparison": dict(self.peer_comparison),
            "regulatory_changes_impact": dict(self.regulatory_changes_impact),
            "recommendations": list(self.recommendations),
        }


@dataclass
class PortfolioRiskSummary:
    """Aggregated risk summary across a portfolio of entities.

    Provides distribution of risk levels, top risk factors, and
    trend summaries for dashboard and reporting use cases.
    """

    total_entities: int = 0
    risk_distribution: dict[str, int] = field(default_factory=dict)
    average_score: float = 0.0
    high_risk_count: int = 0
    critical_risk_count: int = 0
    top_risk_factors: list[dict[str, Any]] = field(default_factory=list)
    trend_summary: Optional[dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.total_entities, int) or self.total_entities < 0:
            raise ValueError("total_entities must be a non-negative integer")
        if not isinstance(self.risk_distribution, dict):
            raise ValueError("risk_distribution must be a dict")
        if not isinstance(self.average_score, int | float) or self.average_score < 0.0 or self.average_score > 100.0:
            raise ValueError("average_score must be between 0 and 100")
        if not isinstance(self.high_risk_count, int) or self.high_risk_count < 0:
            raise ValueError("high_risk_count must be a non-negative integer")
        if not isinstance(self.critical_risk_count, int) or self.critical_risk_count < 0:
            raise ValueError("critical_risk_count must be a non-negative integer")
        if not isinstance(self.top_risk_factors, list):
            raise ValueError("top_risk_factors must be a list")
        if self.trend_summary is not None and not isinstance(self.trend_summary, dict):
            raise ValueError("trend_summary must be a dict or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "risk_distribution": dict(self.risk_distribution),
            "average_score": self.average_score,
            "high_risk_count": self.high_risk_count,
            "critical_risk_count": self.critical_risk_count,
            "top_risk_factors": list(self.top_risk_factors),
            "trend_summary": dict(self.trend_summary) if self.trend_summary else None,
        }


@dataclass
class RegulatoryChangeImpact:
    """Impact assessment of a regulatory change on entity risk profiles.

    Captures the regulation details, affected entities, score delta,
    affected obligations, and recommended remediation actions.
    """

    regulation_id: UUID
    regulation_title: str
    change_description: str
    effective_date: datetime
    impacted_entities: list[UUID] = field(default_factory=list)
    risk_score_delta: float = 0.0
    affected_obligations: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.regulation_id, UUID):
            raise ValueError("regulation_id must be a UUID")
        if not self.regulation_title or not isinstance(self.regulation_title, str):
            raise ValueError("regulation_title must be a non-empty string")
        if not self.change_description or not isinstance(self.change_description, str):
            raise ValueError("change_description must be a non-empty string")
        if not isinstance(self.effective_date, datetime):
            raise ValueError("effective_date must be a datetime")
        if not isinstance(self.impacted_entities, list):
            raise ValueError("impacted_entities must be a list")
        for eid in self.impacted_entities:
            if not isinstance(eid, UUID):
                raise ValueError("each impacted_entity must be a UUID")
        if not isinstance(self.risk_score_delta, int | float):
            raise ValueError("risk_score_delta must be numeric")
        if not isinstance(self.affected_obligations, list):
            raise ValueError("affected_obligations must be a list")
        if not isinstance(self.recommended_actions, list):
            raise ValueError("recommended_actions must be a list")

    def to_dict(self) -> dict[str, Any]:
        return {
            "regulation_id": str(self.regulation_id),
            "regulation_title": self.regulation_title,
            "change_description": self.change_description,
            "effective_date": self.effective_date.isoformat(),
            "impacted_entities": [str(eid) for eid in self.impacted_entities],
            "risk_score_delta": self.risk_score_delta,
            "affected_obligations": list(self.affected_obligations),
            "recommended_actions": list(self.recommended_actions),
        }
