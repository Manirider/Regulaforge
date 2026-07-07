from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class RegulationStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PENDING_REVIEW = "pending_review"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


@dataclass
class ComplianceRequirement:
    id: str = field(default_factory=lambda: str(uuid4()))
    regulation_id: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    mandatory: bool = True
    deadline: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Assessment:
    id: str = field(default_factory=lambda: str(uuid4()))
    regulation_id: str = ""
    entity_id: str = ""
    entity_type: str = "contract"
    status: str = "pending"
    score: float = 0.0
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    assessed_by: str = ""
    assessed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Regulation:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    title: str = ""
    jurisdiction: str = ""
    category: str = ""
    description: str = ""
    status: RegulationStatus = RegulationStatus.DRAFT
    version: str = "1.0"
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    requirements: list[ComplianceRequirement] = field(default_factory=list)
    source_url: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
