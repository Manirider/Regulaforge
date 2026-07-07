"""Domain events for the Explainable AI (XAI) subsystem.

Each event captures a meaningful state change in the explanation
lifecycle, enabling event-driven communication and observability
across the compliance platform.
"""

from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class ExplanationGenerated(DomainEvent):
    """Emitted when a new explanation is successfully generated for a prediction."""

    def __init__(
        self,
        explanation_id: UUID,
        prediction_id: UUID,
        model_name: str,
        explanation_type: str,
        confidence: float,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="xai.explanation.generated",
            aggregate_id=explanation_id,
            aggregate_type="explanation",
            data={
                "prediction_id": str(prediction_id),
                "model_name": model_name,
                "explanation_type": explanation_type,
                "confidence": confidence,
            },
            correlation_id=correlation_id,
        )


class CounterfactualGenerated(DomainEvent):
    """Emitted when a counterfactual explanation is generated."""

    def __init__(
        self,
        counterfactual_id: UUID,
        prediction_id: UUID,
        outcome_change: str,
        distance: float,
        viability: float,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="xai.counterfactual.generated",
            aggregate_id=counterfactual_id,
            aggregate_type="counterfactual_explanation",
            data={
                "prediction_id": str(prediction_id),
                "outcome_change": outcome_change,
                "distance": distance,
                "viability": viability,
            },
            correlation_id=correlation_id,
        )


class ExplanationFailed(DomainEvent):
    """Emitted when explanation generation fails for a prediction."""

    def __init__(
        self,
        prediction_id: UUID,
        explanation_type: str,
        error_message: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="xai.explanation.failed",
            aggregate_id=prediction_id,
            aggregate_type="explanation",
            data={
                "explanation_type": explanation_type,
                "error": error_message,
            },
            correlation_id=correlation_id,
        )
