from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class ContractStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    NEGOTIATION = "negotiation"
    EXECUTED = "executed"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    ARCHIVED = "archived"


@dataclass
class Clause:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    content: str = ""
    type: str = "standard"
    category: str = ""
    version: str = "1.0"
    is_negotiable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContractVersion:
    id: str = field(default_factory=lambda: str(uuid4()))
    contract_id: str = ""
    version_number: int = 1
    content: str = ""
    clauses: list[Clause] = field(default_factory=list)
    changes_summary: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Template:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    category: str = ""
    content: str = ""
    clauses: list[Clause] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    is_published: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Contract:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    status: ContractStatus = ContractStatus.DRAFT
    contract_type: str = "general"
    content: str = ""
    clauses: list[Clause] = field(default_factory=list)
    parties: list[dict[str, Any]] = field(default_factory=list)
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    signed_date: Optional[datetime] = None
    current_version: int = 1
    versions: list[ContractVersion] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
