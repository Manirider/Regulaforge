"""Assessment domain events."""

from typing import Any
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class AssessmentRequested(DomainEvent):
    """Emitted when a compliance assessment is requested."""

    def __init__(self, assessment_id: UUID, entity_id: UUID, **kwargs: Any) -> None:
        super().__init__(
            event_type="assessment.requested",
            aggregate_id=assessment_id,
            aggregate_type="compliance_assessment",
            data={"entity_id": str(entity_id)},
            **kwargs,
        )


class AssessmentStarted(DomainEvent):
    """Emitted when an assessment begins."""

    def __init__(self, assessment_id: UUID, entity_id: UUID, **kwargs: Any) -> None:
        super().__init__(
            event_type="assessment.started",
            aggregate_id=assessment_id,
            aggregate_type="compliance_assessment",
            data={"entity_id": str(entity_id)},
            **kwargs,
        )


class AssessmentCompleted(DomainEvent):
    """Emitted when an assessment is completed and pending review."""

    def __init__(
        self,
        assessment_id: UUID,
        entity_id: UUID,
        score: float,
        finding_count: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="assessment.completed",
            aggregate_id=assessment_id,
            aggregate_type="compliance_assessment",
            data={
                "entity_id": str(entity_id),
                "score": score,
                "finding_count": finding_count,
            },
            **kwargs,
        )


class AssessmentApproved(DomainEvent):
    """Emitted when a completed assessment is approved."""

    def __init__(self, assessment_id: UUID, reviewer_id: UUID, **kwargs: Any) -> None:
        super().__init__(
            event_type="assessment.approved",
            aggregate_id=assessment_id,
            aggregate_type="compliance_assessment",
            data={"reviewer_id": str(reviewer_id)},
            **kwargs,
        )


class ComplianceGapDetected(DomainEvent):
    """Emitted when a compliance gap (finding) is identified."""

    def __init__(
        self,
        assessment_id: UUID,
        finding_id: UUID,
        requirement_code: str,
        risk_level: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="compliance.gap_detected",
            aggregate_id=assessment_id,
            aggregate_type="compliance_assessment",
            data={
                "finding_id": str(finding_id),
                "requirement_code": requirement_code,
                "risk_level": risk_level,
            },
            **kwargs,
        )
