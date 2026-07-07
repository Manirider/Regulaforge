"""Pure domain models for the Temporal Knowledge Graph.

These are NOT SQLAlchemy or ORM models — they are plain Python
dataclasses representing graph nodes, relationships, queries,
and paths with temporal versioning support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class GraphNodeType(str, Enum):
    """Types of nodes in the knowledge graph."""

    REGULATION = "REGULATION"
    CLAUSE = "CLAUSE"
    OBLIGATION = "OBLIGATION"
    ENTITY = "ENTITY"
    AMENDMENT = "AMENDMENT"
    EVENT = "EVENT"
    RISK_FACTOR = "RISK_FACTOR"
    CONTROL = "CONTROL"
    POLICY = "POLICY"
    PROCEDURE = "PROCEDURE"
    EVIDENCE = "EVIDENCE"


class GraphRelationshipType(str, Enum):
    """Types of relationships between nodes in the knowledge graph."""

    AMENDS = "AMENDS"
    SUPERSEDES = "SUPERSEDES"
    REFERENCES = "REFERENCES"
    APPLIES_TO = "APPLIES_TO"
    CREATES_OBLIGATION = "CREATES_OBLIGATION"
    COMPLIES_WITH = "COMPLIES_WITH"
    VIOLATES = "VIOLATES"
    MITIGATES = "MITIGATES"
    DEPENDS_ON = "DEPENDS_ON"
    HAS_INSTANCE = "HAS_INSTANCE"
    DERIVES_FROM = "DERIVES_FROM"
    REPLACES = "REPLACES"


@dataclass
class TemporalNode:
    """A node in the temporal knowledge graph.

    Each node carries temporal validity (valid_from / valid_to)
    enabling point-in-time queries and full version history.
    """

    id: UUID
    node_type: GraphNodeType
    labels: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    valid_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_to: Optional[datetime] = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    embedding: Optional[list[float]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("id must be a UUID")
        if not isinstance(self.node_type, GraphNodeType):
            raise ValueError(f"node_type must be a GraphNodeType, got {type(self.node_type)}")
        if not isinstance(self.labels, list):
            raise ValueError("labels must be a list")
        if not isinstance(self.properties, dict):
            raise ValueError("properties must be a dict")
        if not isinstance(self.valid_from, datetime):
            raise ValueError("valid_from must be a datetime")
        if self.valid_to is not None and not isinstance(self.valid_to, datetime):
            raise ValueError("valid_to must be a datetime or None")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if self.version < 1:
            raise ValueError("version must be >= 1")
        if self.embedding is not None and not isinstance(self.embedding, list):
            raise ValueError("embedding must be a list of floats or None")

    def is_valid_at(self, as_of: datetime) -> bool:
        """Check if this node state is valid at the given point in time."""
        return self.valid_from <= as_of and (self.valid_to is None or self.valid_to > as_of)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return {
            "id": str(self.id),
            "node_type": self.node_type.value,
            "labels": list(self.labels),
            "properties": dict(self.properties),
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "embedding": self.embedding,
        }


@dataclass
class TemporalRelationship:
    """A temporal relationship between two nodes in the knowledge graph."""

    id: UUID
    source_id: UUID
    target_id: UUID
    rel_type: GraphRelationshipType
    properties: dict[str, Any] = field(default_factory=dict)
    valid_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_to: Optional[datetime] = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("id must be a UUID")
        if not isinstance(self.source_id, UUID):
            raise ValueError("source_id must be a UUID")
        if not isinstance(self.target_id, UUID):
            raise ValueError("target_id must be a UUID")
        if not isinstance(self.rel_type, GraphRelationshipType):
            raise ValueError(f"rel_type must be a GraphRelationshipType, got {type(self.rel_type)}")
        if not isinstance(self.properties, dict):
            raise ValueError("properties must be a dict")
        if not isinstance(self.valid_from, datetime):
            raise ValueError("valid_from must be a datetime")
        if self.valid_to is not None and not isinstance(self.valid_to, datetime):
            raise ValueError("valid_to must be a datetime or None")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if self.version < 1:
            raise ValueError("version must be >= 1")

    def is_valid_at(self, as_of: datetime) -> bool:
        """Check if this relationship state is valid at the given point in time."""
        return self.valid_from <= as_of and (self.valid_to is None or self.valid_to > as_of)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return {
            "id": str(self.id),
            "source_id": str(self.source_id),
            "target_id": str(self.target_id),
            "rel_type": self.rel_type.value,
            "properties": dict(self.properties),
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class GraphQuery:
    """A query against the knowledge graph with temporal and semantic support."""

    query_type: str
    filters: dict[str, Any] = field(default_factory=dict)
    temporal_as_of: Optional[datetime] = None
    embedding: Optional[list[float]] = None
    limit: int = 20
    offset: int = 0

    def __post_init__(self) -> None:
        if not self.query_type or not isinstance(self.query_type, str):
            raise ValueError("query_type must be a non-empty string")
        if not isinstance(self.filters, dict):
            raise ValueError("filters must be a dict")
        if self.temporal_as_of is not None and not isinstance(self.temporal_as_of, datetime):
            raise ValueError("temporal_as_of must be a datetime or None")
        if self.embedding is not None and not isinstance(self.embedding, list):
            raise ValueError("embedding must be a list of floats or None")
        if self.limit < 1:
            raise ValueError("limit must be >= 1")
        if self.offset < 0:
            raise ValueError("offset must be >= 0")


@dataclass
class GraphPath:
    """A path through the graph consisting of alternating nodes and relationships."""

    nodes: list[TemporalNode] = field(default_factory=list)
    relationships: list[TemporalRelationship] = field(default_factory=list)
    score: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, list):
            raise ValueError("nodes must be a list of TemporalNode")
        if not isinstance(self.relationships, list):
            raise ValueError("relationships must be a list of TemporalRelationship")
        if not isinstance(self.score, int | float):
            raise ValueError("score must be a numeric value")
        if self.score < 0.0:
            raise ValueError("score must be >= 0.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "relationships": [r.to_dict() for r in self.relationships],
            "score": self.score,
        }
