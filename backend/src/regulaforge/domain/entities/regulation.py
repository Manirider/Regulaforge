"""Regulation entity - the core domain aggregate.

Represents a regulatory document, law, standard, or policy that
organizations must comply with. Regulations are versioned and
can be decomposed into individual requirements and controls.
"""

from datetime import date
from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.entities.base import DomainEntity
from regulaforge.domain.enums import (
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
)


class Regulation(DomainEntity):
    """A regulation, standard, or policy document.

    This is the central aggregate root for the regulation domain.
    Regulations contain requirements and are versioned over time
    as they are amended or superseded.
    """

    def __init__(
        self,
        title: str,
        code: str,
        description: str,
        category: RegulationCategory,
        jurisdiction: RegulationJurisdiction,
        issuing_body: str,
        effective_date: date,
        status: RegulationStatus = RegulationStatus.DRAFT,
        version: str = "1.0",
        tags: Optional[list[str]] = None,
        parent_regulation_id: Optional[UUID] = None,
        superseded_by_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._validate_title(title)
        self._validate_code(code)

        self._title: str = title
        self._code: str = code
        self._description: str = description
        self._category: RegulationCategory = category
        self._jurisdiction: RegulationJurisdiction = jurisdiction
        self._issuing_body: str = issuing_body
        self._effective_date: date = effective_date
        self._status: RegulationStatus = status
        self._version_str: str = version
        self._tags: list[str] = tags or []
        self._parent_regulation_id: Optional[UUID] = parent_regulation_id
        self._superseded_by_id: Optional[UUID] = superseded_by_id
        self._metadata: dict[str, Any] = metadata or {}
        self._requirements: list["RegulationRequirement"] = []

    @staticmethod
    def _validate_title(title: str) -> None:
        """Validate regulation title."""
        if not title or len(title.strip()) < 3:
            raise ValueError("Regulation title must be at least 3 characters")
        if len(title) > 500:
            raise ValueError("Regulation title must not exceed 500 characters")

    @staticmethod
    def _validate_code(code: str) -> None:
        """Validate regulation code."""
        if not code or len(code.strip()) < 2:
            raise ValueError("Regulation code must be at least 2 characters")
        if len(code) > 50:
            raise ValueError("Regulation code must not exceed 50 characters")

    @property
    def title(self) -> str:
        return self._title

    @property
    def code(self) -> str:
        return self._code

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> RegulationCategory:
        return self._category

    @property
    def jurisdiction(self) -> RegulationJurisdiction:
        return self._jurisdiction

    @property
    def issuing_body(self) -> str:
        return self._issuing_body

    @property
    def effective_date(self) -> date:
        return self._effective_date

    @property
    def status(self) -> RegulationStatus:
        return self._status

    @property
    def version_str(self) -> str:
        return self._version_str

    @property
    def tags(self) -> list[str]:
        return list(self._tags)

    @property
    def parent_regulation_id(self) -> Optional[UUID]:
        return self._parent_regulation_id

    @property
    def superseded_by_id(self) -> Optional[UUID]:
        return self._superseded_by_id

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    @property
    def requirements(self) -> list["RegulationRequirement"]:
        return list(self._requirements)

    def add_requirement(self, requirement: "RegulationRequirement") -> None:
        """Add a requirement to this regulation."""
        if not isinstance(requirement, RegulationRequirement):
            raise TypeError("Must be a RegulationRequirement instance")
        if any(r.code == requirement.code for r in self._requirements):
            raise ValueError(f"Requirement with code '{requirement.code}' already exists")
        self._requirements.append(requirement)
        self.mark_updated()

    def remove_requirement(self, requirement_code: str) -> None:
        """Remove a requirement by its code."""
        self._requirements = [r for r in self._requirements if r.code != requirement_code]
        self.mark_updated()

    def publish(self, by: Optional[UUID] = None) -> None:
        """Publish regulation to active state."""
        if self._status != RegulationStatus.DRAFT:
            raise ValueError("Only draft regulations can be published")
        self._status = RegulationStatus.ACTIVE
        self.mark_updated(by)
        from regulaforge.domain.events.regulation import RegulationPublished
        self.register_event(RegulationPublished(
            regulation_id=self._id,
            code=self._code,
            title=self._title,
        ))

    def archive(self, by: Optional[UUID] = None) -> None:
        """Archive this regulation."""
        if self._status in (RegulationStatus.ARCHIVED, RegulationStatus.RETIRED):
            raise ValueError(f"Regulation is already {self._status.value}")
        self._status = RegulationStatus.ARCHIVED
        self.mark_updated(by)

    def supersede(self, new_regulation_id: UUID, by: Optional[UUID] = None) -> None:
        """Mark this regulation as superseded by a newer version."""
        if self._status == RegulationStatus.RETIRED:
            raise ValueError("Cannot supersede a retired regulation")
        self._status = RegulationStatus.SUPERSEDED
        self._superseded_by_id = new_regulation_id
        self.mark_updated(by)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "title": self._title,
            "code": self._code,
            "description": self._description,
            "category": self._category.value,
            "jurisdiction": self._jurisdiction.value,
            "issuing_body": self._issuing_body,
            "effective_date": self._effective_date.isoformat(),
            "status": self._status.value,
            "version": self._version_str,
            "tags": self._tags,
            "parent_regulation_id": str(self._parent_regulation_id) if self._parent_regulation_id else None,
            "superseded_by_id": str(self._superseded_by_id) if self._superseded_by_id else None,
            "metadata": self._metadata,
            "requirements": [r.to_dict() for r in self._requirements],
        })
        return base

    def __repr__(self) -> str:
        return f"<Regulation {self._code}: {self._title[:50]}>"


class RegulationRequirement:
    """A specific requirement/control within a regulation.

    Each regulation is decomposed into individual requirements
    that can be independently assessed for compliance.
    """

    def __init__(
        self,
        code: str,
        title: str,
        description: str,
        parent_requirement_code: Optional[str] = None,
        is_mandatory: bool = True,
        risk_weight: float = 1.0,
        guidance: Optional[str] = None,
        references: Optional[list[str]] = None,
    ) -> None:
        self._validate(code, title, risk_weight)

        self._code: str = code
        self._title: str = title
        self._description: str = description
        self._parent_requirement_code: Optional[str] = parent_requirement_code
        self._is_mandatory: bool = is_mandatory
        self._risk_weight: float = risk_weight
        self._guidance: Optional[str] = guidance
        self._references: list[str] = references or []

    @staticmethod
    def _validate(code: str, title: str, risk_weight: float) -> None:
        if not code or len(code.strip()) < 1:
            raise ValueError("Requirement code is required")
        if not title or len(title.strip()) < 3:
            raise ValueError("Requirement title must be at least 3 characters")
        if risk_weight < 0.0 or risk_weight > 1.0:
            raise ValueError("Risk weight must be between 0.0 and 1.0")

    @property
    def code(self) -> str:
        return self._code

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def parent_requirement_code(self) -> Optional[str]:
        return self._parent_requirement_code

    @property
    def is_mandatory(self) -> bool:
        return self._is_mandatory

    @property
    def risk_weight(self) -> float:
        return self._risk_weight

    @property
    def guidance(self) -> Optional[str]:
        return self._guidance

    @property
    def references(self) -> list[str]:
        return list(self._references)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self._code,
            "title": self._title,
            "description": self._description,
            "parent_requirement_code": self._parent_requirement_code,
            "is_mandatory": self._is_mandatory,
            "risk_weight": self._risk_weight,
            "guidance": self._guidance,
            "references": self._references,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegulationRequirement":
        return cls(
            code=data["code"],
            title=data["title"],
            description=data.get("description", ""),
            parent_requirement_code=data.get("parent_requirement_code"),
            is_mandatory=data.get("is_mandatory", True),
            risk_weight=data.get("risk_weight", 1.0),
            guidance=data.get("guidance"),
            references=data.get("references", []),
        )

    def __repr__(self) -> str:
        return f"<Requirement {self._code}: {self._title[:40]}>"
