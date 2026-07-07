"""Domain events for the Risk Prediction Engine.

Each event captures a meaningful risk-related state change,
enabling event-driven communication with other bounded contexts
such as the Regulation Monitor Agent and notification system.
"""

from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent
from regulaforge.risk_engine.domain.models import RiskLevel


class RiskThresholdBreached(DomainEvent):
    """Emitted when a risk score crosses a configured threshold."""

    def __init__(
        self,
        entity_id: UUID,
        current_score: float,
        threshold_level: RiskLevel,
        threshold_value: float,
        category_scores: dict[str, float],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="risk_engine.threshold.breached",
            aggregate_id=entity_id,
            aggregate_type="entity",
            data={
                "entity_id": str(entity_id),
                "current_score": current_score,
                "threshold_level": threshold_level.value,
                "threshold_value": threshold_value,
                "category_scores": category_scores,
            },
            correlation_id=correlation_id,
        )


class RiskLevelChanged(DomainEvent):
    """Emitted when an entity's risk level changes (e.g. MEDIUM -> HIGH)."""

    def __init__(
        self,
        entity_id: UUID,
        previous_level: RiskLevel,
        new_level: RiskLevel,
        previous_score: float,
        new_score: float,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="risk_engine.risk_level.changed",
            aggregate_id=entity_id,
            aggregate_type="entity",
            data={
                "entity_id": str(entity_id),
                "previous_level": previous_level.value,
                "new_level": new_level.value,
                "previous_score": previous_score,
                "new_score": new_score,
            },
            correlation_id=correlation_id,
        )


class RiskAlertGenerated(DomainEvent):
    """Emitted when a new risk alert is created."""

    def __init__(
        self,
        alert_id: UUID,
        entity_id: UUID,
        alert_type: str,
        severity: RiskLevel,
        message: str,
        details: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="risk_engine.alert.generated",
            aggregate_id=alert_id,
            aggregate_type="risk_alert",
            data={
                "alert_id": str(alert_id),
                "entity_id": str(entity_id),
                "alert_type": alert_type,
                "severity": severity.value,
                "message": message,
                "details": details,
            },
            correlation_id=correlation_id,
        )


class RiskTrendChanged(DomainEvent):
    """Emitted when an entity's risk trend direction changes."""

    def __init__(
        self,
        entity_id: UUID,
        previous_direction: str,
        new_direction: str,
        current_trend_data: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="risk_engine.trend.changed",
            aggregate_id=entity_id,
            aggregate_type="entity",
            data={
                "entity_id": str(entity_id),
                "previous_direction": previous_direction,
                "new_direction": new_direction,
                "current_trend_data": current_trend_data,
            },
            correlation_id=correlation_id,
        )


class PortfolioRiskUpdated(DomainEvent):
    """Emitted when the portfolio-level risk summary is recalculated."""

    def __init__(
        self,
        tenant_id: UUID,
        total_entities: int,
        average_score: float,
        risk_distribution: dict[str, int],
        high_risk_count: int,
        critical_risk_count: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="risk_engine.portfolio.updated",
            aggregate_id=tenant_id,
            aggregate_type="tenant",
            data={
                "tenant_id": str(tenant_id),
                "total_entities": total_entities,
                "average_score": average_score,
                "risk_distribution": risk_distribution,
                "high_risk_count": high_risk_count,
                "critical_risk_count": critical_risk_count,
            },
            correlation_id=correlation_id,
        )


class RegulatoryRiskDetected(DomainEvent):
    """Emitted when a regulatory change introduces new or increased risk."""

    def __init__(
        self,
        regulation_id: UUID,
        regulation_title: str,
        impacted_entity_count: int,
        risk_score_delta: float,
        affected_obligations: list[str],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="risk_engine.regulatory_risk.detected",
            aggregate_id=regulation_id,
            aggregate_type="regulation",
            data={
                "regulation_id": str(regulation_id),
                "regulation_title": regulation_title,
                "impacted_entity_count": impacted_entity_count,
                "risk_score_delta": risk_score_delta,
                "affected_obligations": affected_obligations,
            },
            correlation_id=correlation_id,
        )
