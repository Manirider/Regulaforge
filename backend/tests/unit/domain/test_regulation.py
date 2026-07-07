"""Unit tests for the Regulation domain entity."""

from datetime import date
from uuid import uuid4

import pytest
from regulaforge.config.constants import (
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
)
from regulaforge.domain.entities.regulation import Regulation, RegulationRequirement


class TestRegulationCreation:
    """Tests for Regulation entity creation and validation."""

    def test_create_valid_regulation(self, regulation_data):
        """Should create a regulation with valid data."""
        reg = Regulation(**regulation_data)
        assert reg.title == "General Data Protection Regulation"
        assert reg.code == "GDPR"
        assert reg.status == RegulationStatus.ACTIVE
        assert reg.version_str == "1.0"
        assert reg.version == 1
        assert len(reg.requirements) == 0
        assert reg.id is not None

    def test_create_with_minimal_data(self):
        """Should create a regulation with only required fields."""
        reg = Regulation(
            title="Test Regulation",
            code="TEST-001",
            description="A test regulation",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Test Body",
            effective_date=date(2024, 1, 1),
        )
        assert reg.title == "Test Regulation"
        assert reg.status == RegulationStatus.DRAFT

    def test_reject_empty_title(self):
        """Should reject a regulation with an empty title."""
        with pytest.raises(ValueError, match="at least 3 characters"):
            Regulation(
                title="",
                code="TEST",
                description="Test",
                category=RegulationCategory.GENERAL,
                jurisdiction=RegulationJurisdiction.GLOBAL,
                issuing_body="Test",
                effective_date=date(2024, 1, 1),
            )

    def test_reject_short_code(self):
        """Should reject a regulation with a code that is too short."""
        with pytest.raises(ValueError, match="at least 2 characters"):
            Regulation(
                title="Test Regulation",
                code="",
                description="Test",
                category=RegulationCategory.GENERAL,
                jurisdiction=RegulationJurisdiction.GLOBAL,
                issuing_body="Test",
                effective_date=date(2024, 1, 1),
            )

    def test_entity_equality_by_id(self):
        """Two regulations with the same ID should be equal."""
        id = uuid4()
        reg1 = Regulation(
            id=id, title="Reg A", code="RA", description="Regulation A",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="B", effective_date=date(2024, 1, 1),
        )
        reg2 = Regulation(
            id=id, title="Different Regulation", code="DR", description="Different",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="C", effective_date=date(2024, 1, 1),
        )
        assert reg1 == reg2
        assert hash(reg1) == hash(reg2)


class TestRegulationRequirements:
    """Tests for regulation requirement management."""

    def test_add_requirement(self, regulation):
        """Should add a requirement to a regulation."""
        req = RegulationRequirement(
            code="ART-32",
            title="Security of processing",
            description="Implement appropriate technical measures",
        )
        regulation.add_requirement(req)
        assert len(regulation.requirements) == 3
        assert regulation.requirements[-1].code == "ART-32"

    def test_prevent_duplicate_requirement_code(self, regulation):
        """Should prevent adding a requirement with a duplicate code."""
        with pytest.raises(ValueError, match="already exists"):
            regulation.add_requirement(RegulationRequirement(
                code="ART-5",
                title="Duplicate",
                description="Should not be allowed",
            ))

    def test_remove_requirement(self, regulation):
        """Should remove a requirement by code."""
        regulation.remove_requirement("ART-17")
        codes = [r.code for r in regulation.requirements]
        assert "ART-17" not in codes
        assert len(regulation.requirements) == 1

    def test_requirement_validation(self):
        """Should validate requirement fields."""
        with pytest.raises(ValueError, match="at least 3 characters"):
            RegulationRequirement(
                code="R1",
                title="AB",
                description="Test",
            )

        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            RegulationRequirement(
                code="R1",
                title="Valid Title",
                description="Test",
                risk_weight=5.0,
            )


class TestRegulationLifecycle:
    """Tests for regulation state transitions."""

    def test_publish_draft(self):
        """Should publish a draft regulation."""
        reg = Regulation(
            title="New Regulation",
            code="NEW",
            description="A new regulation",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body",
            effective_date=date(2024, 1, 1),
        )
        assert reg.status == RegulationStatus.DRAFT
        reg.publish()
        assert reg.status == RegulationStatus.ACTIVE

    def test_cannot_publish_active_regulation(self, regulation):
        """Should not publish an already active regulation."""
        with pytest.raises(ValueError, match="Only draft regulations"):
            regulation.publish()

    def test_archive_regulation(self, regulation):
        """Should archive a regulation."""
        regulation.archive()
        assert regulation.status == RegulationStatus.ARCHIVED

    def test_supersede_regulation(self, regulation):
        """Should supersede a regulation with a newer version."""
        new_id = uuid4()
        regulation.supersede(new_id)
        assert regulation.status == RegulationStatus.SUPERSEDED
        assert regulation.superseded_by_id == new_id

    def test_publish_generates_event(self):
        """Should generate a domain event on publish."""
        reg = Regulation(
            title="Test", code="TST", description="Test",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Body", effective_date=date(2024, 1, 1),
        )
        reg.publish()
        events = reg.clear_events()
        assert len(events) == 1
        assert events[0].event_type == "regulation.published"


class TestRegulationSerialization:
    """Tests for regulation serialization."""

    def test_to_dict(self, regulation):
        """Should serialize to dictionary."""
        data = regulation.to_dict()
        assert data["title"] == "General Data Protection Regulation"
        assert data["code"] == "GDPR"
        assert data["status"] == "active"
        assert "requirements" in data
        assert len(data["requirements"]) == 2

    def test_to_dict_includes_timestamps(self, regulation):
        """Should include timestamp information."""
        data = regulation.to_dict()
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert data["version"] == "1.0"
