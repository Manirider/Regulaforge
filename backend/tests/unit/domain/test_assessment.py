"""Unit tests for the ComplianceAssessment domain entity."""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from regulaforge.config.constants import (
    AssessmentStatus,
    ComplianceLevel,
    RiskLevel,
)
from regulaforge.domain.entities.compliance_assessment import (
    ComplianceAssessment,
    ComplianceFinding,
)


class TestAssessmentCreation:
    """Tests for ComplianceAssessment creation and validation."""

    def test_create_valid_assessment(self, assessment_data):
        """Should create an assessment with valid data."""
        assessment = ComplianceAssessment(**assessment_data)
        assert assessment.title == "GDPR Compliance Assessment 2024"
        assert assessment.status == AssessmentStatus.SCHEDULED
        assert assessment.entity_id is not None
        assert len(assessment.regulation_ids) == 1
        assert assessment.overall_score is None
        assert len(assessment.findings) == 0

    def test_reject_empty_title(self):
        """Should reject an assessment with an empty title."""
        with pytest.raises(ValueError, match="at least 3 characters"):
            ComplianceAssessment(
                title="AB",
                entity_id=uuid4(),
                entity_type="organization",
                regulation_ids=[uuid4()],
                assessor_id=uuid4(),
                due_date=date(2024, 12, 31),
            )

    def test_reject_no_regulations(self):
        """Should reject an assessment with no regulations."""
        with pytest.raises(ValueError, match="At least one regulation"):
            ComplianceAssessment(
                title="Valid Assessment",
                entity_id=uuid4(),
                entity_type="organization",
                regulation_ids=[],
                assessor_id=uuid4(),
                due_date=date(2024, 12, 31),
            )


class TestAssessmentLifecycle:
    """Tests for assessment state transitions."""

    def test_start_assessment(self, assessment):
        """Should start a scheduled assessment."""
        assessment.start()
        assert assessment.status == AssessmentStatus.IN_PROGRESS

    def test_cannot_start_non_scheduled(self, assessment):
        """Should not start an assessment that isn't scheduled."""
        assessment.start()
        with pytest.raises(ValueError, match="Cannot start"):
            assessment.start()

    def test_complete_assessment(self, assessment, finding):
        """Should complete an assessment with findings."""
        assessment.start()
        assessment.add_finding(finding)
        assessment.complete(85.0)
        assert assessment.status == AssessmentStatus.PENDING_REVIEW
        assert assessment.overall_score == 85.0
        assert assessment.completed_at is not None

    def test_approve_completed_assessment(self, assessment):
        """Should approve a completed assessment."""
        reviewer_id = uuid4()
        assessment.start()
        assessment.complete(92.0)
        assessment.approve(reviewer_id)
        assert assessment.status == AssessmentStatus.COMPLETED
        assert assessment.approved_by == reviewer_id
        assert assessment.approved_at is not None

    def test_cannot_approve_before_completion(self, assessment):
        """Should not approve an assessment that isn't complete."""
        with pytest.raises(ValueError, match="Can only approve"):
            assessment.approve(uuid4())

    def test_cancel_assessment(self, assessment):
        """Should cancel an assessment."""
        assessment.start()
        assessment.cancel()
        assert assessment.status == AssessmentStatus.CANCELLED

    def test_cannot_cancel_completed(self, assessment):
        """Should not cancel a completed assessment."""
        assessment.start()
        assessment.complete(80.0)
        assessment.approve(uuid4())
        with pytest.raises(ValueError, match="Cannot cancel"):
            assessment.cancel()

    def test_lifecycle_emits_events(self, assessment):
        """Should emit domain events through lifecycle."""
        assessment.start()
        events = assessment.clear_events()
        assert len(events) >= 1
        assert events[0].event_type == "assessment.started"


class TestAssessmentFindings:
    """Tests for finding management within assessments."""

    def test_add_finding(self, assessment, finding_data):
        """Should add a finding to an in-progress assessment."""
        assessment.start()
        finding = ComplianceFinding(**finding_data)
        assessment.add_finding(finding)
        assert len(assessment.findings) == 1
        assert assessment.findings[0].title == "Missing consent mechanism"

    def test_cannot_add_finding_to_scheduled(self, assessment):
        """Should not add findings to a scheduled assessment."""
        finding = ComplianceFinding(
            requirement_code="ART-5",
            title="Test Finding",
            description="Test",
            risk_level=RiskLevel.LOW,
        )
        with pytest.raises(ValueError, match="in-progress"):
            assessment.add_finding(finding)

    def test_finding_risk_calculation(self):
        """Should calculate combined risk score."""
        finding = ComplianceFinding(
            requirement_code="ART-5",
            title="High Risk Finding",
            description="Test",
            risk_level=RiskLevel.HIGH,
            impact_score=9.0,
            likelihood_score=8.0,
        )
        assert finding.risk_score == 72.0

    def test_finding_risk_levels(self, assessment):
        """Should handle findings at different risk levels."""
        assessment.start()

        levels = [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]
        findings_added = []

        for i, level in enumerate(levels):
            finding = ComplianceFinding(
                requirement_code=f"REQ-{i}",
                title=f"Finding {i}",
                description=f"Test finding with {level.value} risk",
                risk_level=level,
            )
            assessment.add_finding(finding)
            findings_added.append(finding)

        # Highest risk findings should return critical first
        top = assessment.get_highest_risk_findings(2)
        assert len(top) == 2
        assert top[0].risk_level == RiskLevel.CRITICAL

    def test_finding_evidence(self, assessment):
        """Should attach evidence to findings."""
        assessment.start()
        finding = ComplianceFinding(
            requirement_code="ART-5",
            title="Finding with evidence",
            description="Test",
            risk_level=RiskLevel.MEDIUM,
        )
        finding.add_evidence({
            "type": "document",
            "reference": "audit-report-2024.pdf",
            "description": "External audit report",
        })
        assessment.add_finding(finding)
        assert len(assessment.findings[0].evidence) == 1


class TestComplianceLevel:
    """Tests for compliance level determination."""

    def test_fully_compliant(self, assessment):
        """Score >= 90 should be fully compliant."""
        assessment.start()
        assessment.complete(95.0)
        assert assessment.get_compliance_level() == ComplianceLevel.FULLY_COMPLIANT

    def test_partially_compliant(self, assessment):
        """Score 70-89 should be partially compliant."""
        assessment.start()
        assessment.complete(75.0)
        assert assessment.get_compliance_level() == ComplianceLevel.PARTIALLY_COMPLIANT

    def test_non_compliant(self, assessment):
        """Score < 50 should be non-compliant."""
        assessment.start()
        assessment.complete(30.0)
        assert assessment.get_compliance_level() == ComplianceLevel.NON_COMPLIANT

    def test_under_review_before_completion(self, assessment):
        """Should be under review when no score yet."""
        assert assessment.get_compliance_level() == ComplianceLevel.UNDER_REVIEW


class TestFindingResolution:
    """Tests for finding resolution workflow."""

    def test_resolve_finding(self):
        """Should mark a finding as resolved."""
        finding = ComplianceFinding(
            requirement_code="ART-5",
            title="Test finding",
            description="Test",
            risk_level=RiskLevel.MEDIUM,
        )
        assert finding.status == "open"
        finding.resolve("Implemented consent management platform")
        assert finding.status == "resolved"

    def test_finding_validation(self):
        """Should validate finding creation."""
        with pytest.raises(ValueError, match="at least 3 characters"):
            ComplianceFinding(
                requirement_code="ART-5",
                title="AB",
                description="Test",
                risk_level=RiskLevel.MEDIUM,
            )

        with pytest.raises(ValueError, match="between 0.0 and 10.0"):
            ComplianceFinding(
                requirement_code="ART-5",
                title="Valid Title",
                description="Test",
                risk_level=RiskLevel.MEDIUM,
                impact_score=15.0,
            )
