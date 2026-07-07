from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class EntityType(str, Enum):
    CONTRACT = "contract"
    REGULATION = "regulation"
    CLAUSE = "clause"
    PARTY = "party"
    OBLIGATION = "obligation"
    RIGHT = "right"
    TERM = "term"
    DOCUMENT = "document"
    USER = "user"
    ORGANIZATION = "organization"
    CUSTOM = "custom"


class RelationshipType(str, Enum):
    REFERENCES = "references"
    GOVERNS = "governs"
    COMPLIES_WITH = "complies_with"
    VIOLATES = "violates"
    DERIVES_FROM = "derives_from"
    AMENDS = "amends"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"
    OWNS = "owns"
    CREATED_BY = "created_by"
    CUSTOM = "custom"


@dataclass
class Entity:
    id: str = field(default_factory=lambda: str(uuid4()))
    type: EntityType = EntityType.CUSTOM
    name: str = ""
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    tenant_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Relationship:
    id: str = field(default_factory=lambda: str(uuid4()))
    source_id: str = ""
    target_id: str = ""
    type: RelationshipType = RelationshipType.RELATED_TO
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GraphQuery:
    entity_type: Optional[EntityType] = None
    relationship_type: Optional[RelationshipType] = None
    max_depth: int = 2
    limit: int = 100
    filters: dict[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
