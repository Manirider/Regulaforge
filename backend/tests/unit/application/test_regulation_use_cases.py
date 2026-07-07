"""Unit tests for regulation use cases."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from regulaforge.application.use_cases.regulation_use_cases import (
    AddRequirementUseCase,
    CreateRegulationUseCase,
    GetRegulationUseCase,
    PublishRegulationUseCase,
    SearchRegulationsUseCase,
    UpdateRegulationUseCase,
)
from regulaforge.config.constants import (
    RegulationCategory,
    RegulationJurisdiction,
)
from regulaforge.domain.entities.regulation import Regulation
from regulaforge.domain.repositories.base import DuplicateEntityError, EntityNotFoundError


class TestCreateRegulationUseCase:
    """Tests for the CreateRegulationUseCase."""

    async def test_create_regulation_success(
        self, mock_regulation_repo, mock_event_publisher, regulation_data
    ):
        """Should create a regulation successfully."""
        use_case = CreateRegulationUseCase(
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        mock_regulation_repo.get_by_code.return_value = None
        mock_regulation_repo.save.return_value = Regulation(
            id=uuid4(),
            **regulation_data,
        )

        result = await use_case.execute(
            title=regulation_data["title"],
            code=regulation_data["code"],
            description=regulation_data["description"],
            category=regulation_data["category"],
            jurisdiction=regulation_data["jurisdiction"],
            issuing_body=regulation_data["issuing_body"],
            effective_date=regulation_data["effective_date"],
            created_by=uuid4(),
        )

        assert result.code == "GDPR"
        assert result.title == "General Data Protection Regulation"
        mock_regulation_repo.save.assert_called_once()

    async def test_create_duplicate_regulation(
        self, mock_regulation_repo, mock_event_publisher, regulation
    ):
        """Should reject duplicate regulation codes."""
        use_case = CreateRegulationUseCase(
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        mock_regulation_repo.get_by_code.return_value = regulation

        with pytest.raises(DuplicateEntityError):
            await use_case.execute(
                title="GDPR",
                code="GDPR",
                description="Duplicate",
                category=RegulationCategory.DATA_PROTECTION,
                jurisdiction=RegulationJurisdiction.EU,
                issuing_body="EU",
                effective_date=date(2024, 1, 1),
                created_by=uuid4(),
            )

    async def test_creates_event_on_success(
        self, mock_regulation_repo, mock_event_publisher, regulation_data
    ):
        """Should publish a domain event after creation."""
        use_case = CreateRegulationUseCase(
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        mock_regulation_repo.get_by_code.return_value = None
        mock_regulation_repo.save.return_value = Regulation(
            id=uuid4(),
            **regulation_data,
        )

        await use_case.execute(
            title=regulation_data["title"],
            code=regulation_data["code"],
            description=regulation_data["description"],
            category=regulation_data["category"],
            jurisdiction=regulation_data["jurisdiction"],
            issuing_body=regulation_data["issuing_body"],
            effective_date=regulation_data["effective_date"],
            created_by=uuid4(),
        )

        assert mock_event_publisher.publish.called


class TestGetRegulationUseCase:
    """Tests for the GetRegulationUseCase."""

    async def test_get_existing_regulation(self, mock_regulation_repo, regulation):
        """Should retrieve an existing regulation."""
        use_case = GetRegulationUseCase(regulation_repo=mock_regulation_repo)
        mock_regulation_repo.get_by_id.return_value = regulation

        result = await use_case.execute(regulation.id)
        assert result.id == regulation.id
        assert result.code == "GDPR"

    async def test_get_nonexistent_regulation(self, mock_regulation_repo):
        """Should raise EntityNotFoundError for missing regulation."""
        use_case = GetRegulationUseCase(regulation_repo=mock_regulation_repo)
        mock_regulation_repo.get_by_id.return_value = None

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(uuid4())


class TestPublishRegulationUseCase:
    """Tests for the PublishRegulationUseCase."""

    async def test_publish_draft(self, mock_regulation_repo, mock_event_publisher):
        """Should publish a draft regulation."""
        from regulaforge.config.constants import RegulationStatus

        use_case = PublishRegulationUseCase(
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        reg = Regulation(
            title="Draft Reg",
            code="DRAFT",
            description="A draft",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Test",
            effective_date=date(2024, 1, 1),
        )
        mock_regulation_repo.get_by_id.return_value = reg
        mock_regulation_repo.save.return_value = reg

        result = await use_case.execute(reg.id, uuid4())
        assert result.status == RegulationStatus.ACTIVE
        mock_regulation_repo.save.assert_called_once()


class TestAddRequirementUseCase:
    """Tests for the AddRequirementUseCase."""

    async def test_add_requirement(
        self, mock_regulation_repo, mock_event_publisher, regulation
    ):
        """Should add a requirement to a regulation."""
        use_case = AddRequirementUseCase(
            regulation_repo=mock_regulation_repo,
            event_publisher=mock_event_publisher,
        )

        mock_regulation_repo.get_by_id.return_value = regulation
        mock_regulation_repo.save.return_value = regulation

        result = await use_case.execute(
            regulation_id=regulation.id,
            code="ART-32",
            title="Security of processing",
            description="Implement appropriate security measures",
            added_by=uuid4(),
        )

        assert result is not None
        mock_regulation_repo.save.assert_called_once()
