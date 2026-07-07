"""Compliance Assessment aggregate.

Models the process of evaluating an entity's compliance against
a set of regulation requirements. Tracks findings, evidence,
remediations, and the overall compliance posture.
"""

from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.entities.base import DomainEntity
from regulaforge.domain.enums import (
    AssessmentStatus,
    ComplianceLevel,
    RiskLevel,
)


class ComplianceAssessment(DomainEntity):
    """A compliance assessment evaluating an entity against regulations.

    This aggregate root orchestrates the assessment process including
    evidence collection, finding identification, risk scoring, and
    remediation tracking.
    """

    def __init__(
        self,
        title: str,
        entity_id: UUID,
        entity_type: str,
        regulation_ids: list[UUID],
        assessor_id: UUID,
        due_date: date,
        status: AssessmentStatus = AssessmentStatus.SCHEDULED,
        scope_description: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._validate(title, entity_id, regulation_ids, assessor_id)

        self._title: str = title
        self._entity_id: UUID = entity_id
        self._entity_type: str = entity_type
        self._regulation_ids: list[UUID] = regulation_ids
        self._assessor_id: UUID = assessor_id
        self._due_date: date = due_date
        self._status: AssessmentStatus = status
        self._scope_description: Optional[str] = scope_description
        self._metadata: dict[str, Any] = metadata or {}
        self._findings: list["ComplianceFinding"] = []
        self._approved_by: Optional[UUID] = None
        self._approved_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._overall_score: Optional[float] = None

    @staticmethod
    def _validate(title: str, entity_id: UUID, regulation_ids: list[UUID], assessor_id: UUID) -> None:
        if not title or len(title.strip()) < 3:
            raise ValueError("Assessment title must be at least 3 characters")
        if not entity_id:
            raise ValueError("Entity ID is required")
        if not regulation_ids:
            raise ValueError("At least one regulation ID is required")
        if not assessor_id:
            raise ValueError("Assessor ID is required")

    @property
    def title(self) -> str:
        return self._title

    @property
    def entity_id(self) -> UUID:
        return self._entity_id

    @property
    def entity_type(self) -> str:
        return self._entity_type

    @property
    def regulation_ids(self) -> list[UUID]:
        return list(self._regulation_ids)

    @property
    def assessor_id(self) -> UUID:
        return self._assessor_id

    @property
    def due_date(self) -> date:
        return self._due_date

    @property
    def status(self) -> AssessmentStatus:
        return self._status

    @property
    def scope_description(self) -> Optional[str]:
        return self._scope_description

    @property
    def findings(self) -> list["ComplianceFinding"]:
        return list(self._findings)

    @property
    def approved_by(self) -> Optional[UUID]:
        return self._approved_by

    @property
    def approved_at(self) -> Optional[datetime]:
        return self._approved_at

    @property
    def completed_at(self) -> Optional[datetime]:
        return self._completed_at

    @property
    def overall_score(self) -> Optional[float]:
        return self._overall_score

    def start(self, by: Optional[UUID] = None) -> None:
        """Start the assessment."""
        if self._status != AssessmentStatus.SCHEDULED:
            raise ValueError(f"Cannot start assessment in status '{self._status.value}'")
        self._status = AssessmentStatus.IN_PROGRESS
        self.mark_updated(by)
        from regulaforge.domain.events.assessment import AssessmentStarted
        self.register_event(AssessmentStarted(
            assessment_id=self._id,
            entity_id=self._entity_id,
        ))

    def add_finding(self, finding: "ComplianceFinding") -> None:
        """Add a compliance finding to this assessment."""
        if not isinstance(finding, ComplianceFinding):
            raise TypeError("Must be a ComplianceFinding instance")
        if self._status not in (AssessmentStatus.IN_PROGRESS, AssessmentStatus.PENDING_REVIEW):
            raise ValueError("Can only add findings to in-progress assessments")
        self._findings.append(finding)
        self.mark_updated()

    def complete(self, score: float, by: Optional[UUID] = None) -> None:
        """Complete the assessment with a final score."""
        if self._status != AssessmentStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete assessment in status '{self._status.value}'")
        if score < 0.0 or score > 100.0:
            raise ValueError("Score must be between 0 and 100")

        self._overall_score = score
        self._status = AssessmentStatus.PENDING_REVIEW
        self._completed_at = datetime.now(timezone.utc)
        self.mark_updated(by)

        from regulaforge.domain.events.assessment import AssessmentCompleted
        self.register_event(AssessmentCompleted(
            assessment_id=self._id,
            entity_id=self._entity_id,
            score=score,
            finding_count=len(self._findings),
        ))

    def approve(self, reviewer_id: UUID) -> None:
        """Approve the completed assessment."""
        if self._status != AssessmentStatus.PENDING_REVIEW:
            raise ValueError("Can only approve assessments pending review")
        self._status = AssessmentStatus.COMPLETED
        self._approved_by = reviewer_id
        self._approved_at = datetime.now(timezone.utc)
        self.mark_updated(reviewer_id)

    def reject(self, reviewer_id: UUID, _reason: str) -> None:
        """Reject and send back for revision."""
        if self._status != AssessmentStatus.PENDING_REVIEW:
            raise ValueError("Can only reject assessments pending review")
        self._status = AssessmentStatus.IN_PROGRESS
        self.mark_updated(reviewer_id)

    def cancel(self, by: Optional[UUID] = None) -> None:
        """Cancel this assessment."""
        if self._status in (AssessmentStatus.COMPLETED, AssessmentStatus.CANCELLED):
            raise ValueError(f"Cannot cancel assessment in status '{self._status.value}'")
        self._status = AssessmentStatus.CANCELLED
        self.mark_updated(by)

    def get_compliance_level(self) -> ComplianceLevel:
        """Derive the overall compliance level from the score."""
        if self._overall_score is None:
            return ComplianceLevel.UNDER_REVIEW
        if self._overall_score >= 90:
            return ComplianceLevel.FULLY_COMPLIANT
        elif self._overall_score >= 70:
            return ComplianceLevel.PARTIALLY_COMPLIANT
        elif self._overall_score >= 50:
            return ComplianceLevel.NON_COMPLIANT
        return ComplianceLevel.NON_COMPLIANT

    def get_highest_risk_findings(self, limit: int = 5) -> list["ComplianceFinding"]:
        """Return the highest risk findings, sorted by severity."""
        sorted_findings = sorted(
            self._findings,
            key=lambda f: (RiskLevelOrder.get(f.risk_level, 99), f.impact_score or 0),
            reverse=True,
        )
        return sorted_findings[:limit]

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "title": self._title,
            "entity_id": str(self._entity_id),
            "entity_type": self._entity_type,
            "regulation_ids": [str(rid) for rid in self._regulation_ids],
            "assessor_id": str(self._assessor_id),
            "due_date": self._due_date.isoformat(),
            "status": self._status.value,
            "scope_description": self._scope_description,
            "findings": [f.to_dict() for f in self._findings],
            "approved_by": str(self._approved_by) if self._approved_by else None,
            "approved_at": self._approved_at.isoformat() if self._approved_at else None,
            "completed_at": self._completed_at.isoformat() if self._completed_at else None,
            "overall_score": self._overall_score,
            "compliance_level": self.get_compliance_level().value,
        })
        return base

    def __repr__(self) -> str:
        return f"<ComplianceAssessment {self._title[:40]} [{self._status.value}]>"


# Risk level ordering for sorting
RiskLevelOrder: dict[RiskLevel, int] = {
    RiskLevel.CRITICAL: 5,
    RiskLevel.HIGH: 4,
    RiskLevel.MEDIUM: 3,
    RiskLevel.LOW: 2,
    RiskLevel.NEGLIGIBLE: 1,
}


class ComplianceFinding(DomainEntity):
    """A specific finding identified during a compliance assessment.

    Findings represent gaps, non-conformities, or observations
    discovered when assessing an entity against regulation requirements.
    """

    def __init__(
        self,
        requirement_code: str,
        title: str,
        description: str,
        risk_level: RiskLevel,
        status: str = "open",
        impact_score: Optional[float] = None,
        likelihood_score: Optional[float] = None,
        evidence: Optional[list[dict[str, Any]]] = None,
        remediation_recommendation: Optional[str] = None,
        remediation_due_date: Optional[date] = None,
        assigned_to: Optional[UUID] = None,
        category: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._validate(requirement_code, title, risk_level, impact_score, likelihood_score)

        self._requirement_code: str = requirement_code
        self._title: str = title
        self._description: str = description
        self._risk_level: RiskLevel = risk_level
        self._status: str = status
        self._impact_score: Optional[float] = impact_score
        self._likelihood_score: Optional[float] = likelihood_score
        self._evidence: list[dict[str, Any]] = evidence or []
        self._remediation_recommendation: Optional[str] = remediation_recommendation
        self._remediation_due_date: Optional[date] = remediation_due_date
        self._assigned_to: Optional[UUID] = assigned_to
        self._category: Optional[str] = category
        self._resolved_at: Optional[datetime] = None

    @staticmethod
    def _validate(
        requirement_code: str,
        title: str,
        risk_level: RiskLevel,
        impact_score: Optional[float],
        likelihood_score: Optional[float],
    ) -> None:
        if not requirement_code:
            raise ValueError("Requirement code is required")
        if not title or len(title.strip()) < 3:
            raise ValueError("Finding title must be at least 3 characters")
        if not isinstance(risk_level, RiskLevel):
            raise TypeError("Invalid risk level")
        if impact_score is not None and (impact_score < 0.0 or impact_score > 10.0):
            raise ValueError("Impact score must be between 0.0 and 10.0")
        if likelihood_score is not None and (likelihood_score < 0.0 or likelihood_score > 10.0):
            raise ValueError("Likelihood score must be between 0.0 and 10.0")

    @property
    def requirement_code(self) -> str:
        return self._requirement_code

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def risk_level(self) -> RiskLevel:
        return self._risk_level

    @property
    def status(self) -> str:
        return self._status

    @property
    def impact_score(self) -> Optional[float]:
        return self._impact_score

    @property
    def likelihood_score(self) -> Optional[float]:
        return self._likelihood_score

    @property
    def evidence(self) -> list[dict[str, Any]]:
        return list(self._evidence)

    @property
    def remediation_recommendation(self) -> Optional[str]:
        return self._remediation_recommendation

    @property
    def risk_score(self) -> Optional[float]:
        """Calculate composite risk score."""
        if self._impact_score is not None and self._likelihood_score is not None:
            return self._impact_score * self._likelihood_score
        return None

    def resolve(self, _resolution_notes: str, by: Optional[UUID] = None) -> None:
        """Mark this finding as resolved."""
        self._status = "resolved"
        self._resolved_at = datetime.now(timezone.utc)
        self.mark_updated(by)

    def add_evidence(self, artifact: dict[str, Any]) -> None:
        """Attach evidence artifact to this finding."""
        if not artifact.get("type") or not artifact.get("reference"):
            raise ValueError("Evidence must have type and reference")
        self._evidence.append(artifact)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "requirement_code": self._requirement_code,
            "title": self._title,
            "description": self._description,
            "risk_level": self._risk_level.value,
            "status": self._status,
            "impact_score": self._impact_score,
            "likelihood_score": self._likelihood_score,
            "risk_score": self.risk_score,
            "evidence": self._evidence,
            "remediation_recommendation": self._remediation_recommendation,
            "remediation_due_date": self._remediation_due_date.isoformat() if self._remediation_due_date else None,
            "assigned_to": str(self._assigned_to) if self._assigned_to else None,
            "category": self._category,
            "resolved_at": self._resolved_at.isoformat() if self._resolved_at else None,
        })
        return base
