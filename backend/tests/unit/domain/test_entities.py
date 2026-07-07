"""Unit tests for domain entities.

Tests business rules, invariants, and state transitions
for all domain aggregates.
"""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from regulaforge.domain.entities.compliance_assessment import ComplianceAssessment, ComplianceFinding
from regulaforge.domain.entities.document import Document
from regulaforge.domain.entities.entity import AssessableEntity
from regulaforge.domain.entities.regulation import Regulation, RegulationRequirement
from regulaforge.domain.entities.role import Permission, Role, UserRole
from regulaforge.domain.entities.tenant import Tenant
from regulaforge.domain.enums import (
    ArtifactType,
    AssessmentStatus,
    ComplianceLevel,
    EntityType,
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
    RiskLevel,
)

# =============================================================================
# Regulation Entity Tests
# =============================================================================


class TestRegulationCreation:
    def test_create_minimal_regulation(self):
        r = Regulation(
            title="GDPR",
            code="GDPR",
            description="General Data Protection Regulation",
            category=RegulationCategory.DATA_PROTECTION,
            jurisdiction=RegulationJurisdiction.EU,
            issuing_body="European Commission",
            effective_date=date(2018, 5, 25),
        )
        assert r.title == "GDPR"
        assert r.code == "GDPR"
        assert r.status == RegulationStatus.DRAFT
        assert r.version_str == "1.0"
        assert len(r.requirements) == 0
        assert r.parent_regulation_id is None
        assert r.superseded_by_id is None

    def test_title_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 3 characters"):
            Regulation(
                title="AB",
                code="GDPR",
                description="d",
                category=RegulationCategory.GENERAL,
                jurisdiction=RegulationJurisdiction.GLOBAL,
                issuing_body="Body",
                effective_date=date.today(),
            )

    def test_code_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 2 characters"):
            Regulation(
                title="Valid Title",
                code="X",
                description="d",
                category=RegulationCategory.GENERAL,
                jurisdiction=RegulationJurisdiction.GLOBAL,
                issuing_body="Body",
                effective_date=date.today(),
            )


class TestRegulationLifecycle:
    def test_publish_draft(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r.publish()
        assert r.status == RegulationStatus.ACTIVE

    def test_cannot_publish_already_active(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r.publish()
        with pytest.raises(ValueError, match="Only draft"):
            r.publish()

    def test_archive_active(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r.publish()
        r.archive()
        assert r.status == RegulationStatus.ARCHIVED

    def test_cannot_archive_archived(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r.archive()
        with pytest.raises(ValueError, match="already"):
            r.archive()

    def test_supersede(self):
        r1 = Regulation(
            title="Old",
            code="OLD",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r1.publish()
        new_id = uuid4()
        r1.supersede(new_id)
        assert r1.status == RegulationStatus.SUPERSEDED
        assert r1.superseded_by_id == new_id

    def test_register_and_clear_events(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r.publish()
        events = r.clear_events()
        assert len(events) == 1
        assert events[0].event_type == "regulation.published"
        assert r.clear_events() == []


class TestRegulationRequirements:
    def test_add_requirement(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        req = RegulationRequirement(
            code="ART.1",
            title="Article 1",
            description="First article",
        )
        r.add_requirement(req)
        assert len(r.requirements) == 1
        assert r.requirements[0].code == "ART.1"

    def test_add_duplicate_code_raises(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r.add_requirement(RegulationRequirement("ART.1", "Art 1", "d"))
        with pytest.raises(ValueError, match="already exists"):
            r.add_requirement(RegulationRequirement("ART.1", "Art 1 dup", "d"))

    def test_remove_requirement(self):
        r = Regulation(
            title="Test",
            code="TEST",
            description="d",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date.today(),
        )
        r.add_requirement(RegulationRequirement("ART.1", "Art 1", "d"))
        r.add_requirement(RegulationRequirement("ART.2", "Art 2", "d"))
        r.remove_requirement("ART.1")
        assert len(r.requirements) == 1
        assert r.requirements[0].code == "ART.2"


# =============================================================================
# Compliance Assessment Entity Tests
# =============================================================================


class TestAssessmentCreation:
    def test_create_minimal(self):
        entity_id = uuid4()
        regulation_ids = [uuid4()]
        a = ComplianceAssessment(
            title="Q1 Audit",
            entity_id=entity_id,
            entity_type="organization",
            regulation_ids=regulation_ids,
            assessor_id=uuid4(),
            due_date=date(2025, 6, 30),
        )
        assert a.title == "Q1 Audit"
        assert a.entity_id == entity_id
        assert a.regulation_ids == regulation_ids
        assert a.status == AssessmentStatus.SCHEDULED
        assert a.overall_score is None
        assert a.completed_at is None

    def test_title_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 3 characters"):
            ComplianceAssessment(
                title="AB",
                entity_id=uuid4(),
                entity_type="org",
                regulation_ids=[uuid4()],
                assessor_id=uuid4(),
                due_date=date.today(),
            )

    def test_no_regulations_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            ComplianceAssessment(
                title="Valid",
                entity_id=uuid4(),
                entity_type="org",
                regulation_ids=[],
                assessor_id=uuid4(),
                due_date=date.today(),
            )


class TestAssessmentLifecycle:
    def test_full_lifecycle(self):
        a = ComplianceAssessment(
            title="Audit",
            entity_id=uuid4(),
            entity_type="org",
            regulation_ids=[uuid4()],
            assessor_id=uuid4(),
            due_date=date.today(),
        )
        assert a.status == AssessmentStatus.SCHEDULED

        a.start()
        assert a.status == AssessmentStatus.IN_PROGRESS

        finding = ComplianceFinding(
            requirement_code="ART.1",
            title="Missing control",
            description="Control not implemented",
            risk_level=RiskLevel.HIGH,
        )
        a.add_finding(finding)
        assert len(a.findings) == 1

        a.complete(score=75.0)
        assert a.status == AssessmentStatus.PENDING_REVIEW
        assert a.overall_score == 75.0
        assert a.completed_at is not None

        a.approve(reviewer_id=uuid4())
        assert a.status == AssessmentStatus.COMPLETED

    def test_cannot_cancel_completed(self):
        a = ComplianceAssessment(
            title="Audit",
            entity_id=uuid4(),
            entity_type="org",
            regulation_ids=[uuid4()],
            assessor_id=uuid4(),
            due_date=date.today(),
        )
        a.start()
        a.complete(100.0)
        a.approve(uuid4())
        with pytest.raises(ValueError, match="Cannot cancel"):
            a.cancel()

    def test_compliance_level_derivation(self):
        a = ComplianceAssessment(
            title="Audit",
            entity_id=uuid4(),
            entity_type="org",
            regulation_ids=[uuid4()],
            assessor_id=uuid4(),
            due_date=date.today(),
        )
        assert a.get_compliance_level() == ComplianceLevel.UNDER_REVIEW
        a.start()
        a.complete(95.0)
        assert a.get_compliance_level() == ComplianceLevel.FULLY_COMPLIANT


class TestComplianceFinding:
    def test_create(self):
        f = ComplianceFinding(
            requirement_code="ART.1",
            title="Missing firewall",
            description="No firewall deployed",
            risk_level=RiskLevel.CRITICAL,
            impact_score=9.0,
            likelihood_score=8.0,
        )
        assert f.title == "Missing firewall"
        assert f.risk_level == RiskLevel.CRITICAL
        assert f.risk_score == 72.0
        assert f.status == "open"

    def test_invalid_risk_level_raises(self):
        with pytest.raises(TypeError):
            ComplianceFinding(
                requirement_code="ART.1",
                title="Finding",
                description="d",
                risk_level="invalid",  # type: ignore
            )

    def test_resolve(self):
        f = ComplianceFinding(
            requirement_code="ART.1",
            title="Finding",
            description="d",
            risk_level=RiskLevel.LOW,
        )
        f.resolve("Fixed")
        assert f.status == "resolved"


# =============================================================================
# Entity Tests
# =============================================================================


class TestAssessableEntity:
    def test_create(self):
        tenant_id = uuid4()
        e = AssessableEntity(
            name="Marketing Dept",
            entity_type=EntityType.DEPARTMENT,
            tenant_id=tenant_id,
        )
        assert e.name == "Marketing Dept"
        assert e.entity_type == EntityType.DEPARTMENT
        assert e.tenant_id == tenant_id
        assert e.is_active is True

    def test_deactivate(self):
        e = AssessableEntity(
            name="Dept",
            entity_type=EntityType.DEPARTMENT,
            tenant_id=uuid4(),
        )
        e.deactivate()
        assert e.is_active is False

    def test_reactivate(self):
        e = AssessableEntity(
            name="Dept",
            entity_type=EntityType.DEPARTMENT,
            tenant_id=uuid4(),
        )
        e.deactivate()
        e.activate()
        assert e.is_active is True

    def test_name_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 2 characters"):
            AssessableEntity(
                name="X",
                entity_type=EntityType.DEPARTMENT,
                tenant_id=uuid4(),
            )

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            AssessableEntity(
                name="Dept",
                entity_type="not_an_entity_type",  # type: ignore
                tenant_id=uuid4(),
            )


# =============================================================================
# Document Entity Tests
# =============================================================================


class TestDocument:
    def test_create(self):
        d = Document(
            title="Policy Document",
            file_name="policy.pdf",
            file_path="/uploads/policy.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            artifact_type=ArtifactType.DOCUMENT,
            tenant_id=uuid4(),
            uploaded_by=uuid4(),
        )
        assert d.title == "Policy Document"
        assert d.is_verified is False
        assert d.processing_status == "pending"

    def test_verify(self):
        d = Document(
            title="Doc",
            file_name="doc.pdf",
            file_path="/uploads/doc.pdf",
            mime_type="application/pdf",
            file_size_bytes=512,
            artifact_type=ArtifactType.POLICY,
            tenant_id=uuid4(),
            uploaded_by=uuid4(),
        )
        verifier = uuid4()
        d.verify(verifier)
        assert d.is_verified is True
        assert d.verified_by == verifier

    def test_cannot_verify_twice(self):
        d = Document(
            title="Doc",
            file_name="doc.pdf",
            file_path="/uploads/doc.pdf",
            mime_type="application/pdf",
            file_size_bytes=512,
            artifact_type=ArtifactType.POLICY,
            tenant_id=uuid4(),
            uploaded_by=uuid4(),
        )
        d.verify(uuid4())
        with pytest.raises(ValueError, match="already verified"):
            d.verify(uuid4())

    def test_invalid_file_size_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Document(
                title="Doc",
                file_name="doc.pdf",
                file_path="/uploads/doc.pdf",
                mime_type="application/pdf",
                file_size_bytes=0,
                artifact_type=ArtifactType.DOCUMENT,
                tenant_id=uuid4(),
                uploaded_by=uuid4(),
            )


# =============================================================================
# Tenant Entity Tests
# =============================================================================


class TestTenant:
    def test_create(self):
        t = Tenant(name="Acme Corp", slug="acme-corp")
        assert t.name == "Acme Corp"
        assert t.slug == "acme-corp"
        assert t.is_active is True

    def test_invalid_slug_raises(self):
        with pytest.raises(ValueError, match="Slug must contain"):
            Tenant(name="Acme", slug="INVALID SLUG!")

    def test_deactivate(self):
        t = Tenant(name="Acme", slug="acme")
        t.deactivate()
        assert t.is_active is False

    def test_settings(self):
        t = Tenant(name="Acme", slug="acme", settings={"timezone": "UTC"})
        assert t.get_setting("timezone") == "UTC"
        t.update_settings({"timezone": "EST"})
        assert t.get_setting("timezone") == "EST"


# =============================================================================
# Role / Permission Entity Tests
# =============================================================================


class TestPermission:
    def test_from_string(self):
        p = Permission.from_string("regulation:create")
        assert p.resource == "regulation"
        assert p.action == "create"
        assert p.key == "regulation:create"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="resource:action"):
            Permission.from_string("invalid")


class TestRole:
    def test_create(self):
        r = Role(name="admin", description="Admin role", permissions=["user:read", "user:write"])
        assert r.name == "admin"
        assert "user:read" in r.permissions
        assert r.is_system_role is False

    def test_has_permission(self):
        r = Role(name="auditor", permissions=["assessment:read"])
        assert r.has_permission("assessment:read") is True
        assert r.has_permission("assessment:write") is False

    def test_add_permission(self):
        r = Role(name="custom", permissions=[])
        r.add_permission("report:read")
        assert "report:read" in r.permissions

    def test_cannot_modify_system_role(self):
        r = Role(name="admin", is_system_role=True)
        with pytest.raises(ValueError, match="Cannot modify"):
            r.add_permission("user:write")

    def test_set_permissions_replaces(self):
        r = Role(name="custom", permissions=["old:perm"])
        r.set_permissions(["new:perm"])
        assert r.permissions == ["new:perm"]


# =============================================================================
# Auth / Password Policy Tests
# =============================================================================


class TestPasswordPolicy:
    from regulaforge.domain.services.password_policy import PasswordPolicy

    def test_valid_password(self):
        result = self.PasswordPolicy.validate("ValidP@ss123")
        assert result.is_valid is True

    def test_too_short(self):
        result = self.PasswordPolicy.validate("Ab1@")
        assert result.is_valid is False
        assert any("at least 12" in e for e in result.errors)

    def test_missing_uppercase(self):
        result = self.PasswordPolicy.validate("lowercase1@#$%^&")
        assert result.is_valid is False
        assert any("uppercase" in e for e in result.errors)

    def test_missing_lowercase(self):
        result = self.PasswordPolicy.validate("UPPERCASE1@#$%^&")
        assert result.is_valid is False
        assert any("lowercase" in e for e in result.errors)

    def test_missing_digit(self):
        result = self.PasswordPolicy.validate("NoDigitHere!@#")
        assert result.is_valid is False
        assert any("digit" in e for e in result.errors)

    def test_missing_special(self):
        result = self.PasswordPolicy.validate("NoSpecialChar1")
        assert result.is_valid is False
        assert any("special" in e for e in result.errors)
