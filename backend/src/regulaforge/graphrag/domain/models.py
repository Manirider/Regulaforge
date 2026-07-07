from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from regulaforge.graphrag.domain.enums import (
    EntityCategory,
    GraphNodeLabel,
    GraphRelationshipType,
    RetrievalStrategy,
    TemporalRelation,
)


@dataclass
class DocumentNode:
    id: str
    title: str
    source: str
    doc_type: str
    jurisdiction: Optional[str] = None
    regulatory_body: Optional[str] = None
    published_date: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ChunkNode:
    id: str
    document_id: str
    text: str
    chunk_index: int
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    page_number: Optional[int] = None
    heading: Optional[str] = None


@dataclass
class EntityNode:
    id: str
    name: str
    category: EntityCategory
    aliases: list[str] = field(default_factory=list)
    description: Optional[str] = None
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


@dataclass
class RelationshipEdge:
    source_id: str
    target_id: str
    relationship_type: GraphRelationshipType
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    temporal_context: Optional[str] = None


@dataclass
class TemporalEvent:
    id: str
    name: str
    date: datetime
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    entity_ids: list[str] = field(default_factory=list)
    event_type: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphPath:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    length: int
    score: float = 1.0


@dataclass
class GraphQuery:
    node_labels: Optional[list[GraphNodeLabel]] = None
    relationship_types: Optional[list[GraphRelationshipType]] = None
    entity_names: Optional[list[str]] = None
    entity_categories: Optional[list[EntityCategory]] = None
    max_depth: int = 3
    min_confidence: float = 0.0
    limit: int = 20


@dataclass
class TemporalQuery:
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    relation: TemporalRelation = TemporalRelation.DURING
    entity_names: Optional[list[str]] = None
    event_types: Optional[list[str]] = None
    limit: int = 20


@dataclass
class TraversalConfig:
    max_depth: int = 3
    min_weight: float = 0.0
    max_branches: int = 10
    traversal_strategy: str = "bfs"
    include_metadata: bool = True


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    strategy: RetrievalStrategy
    source: str
    page_number: Optional[int] = None
    heading: Optional[str] = None
    entities: list[EntityNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RankedResult:
    result: RetrievalResult
    rank: int
    rerank_score: float
    original_score: float


@dataclass
class Citation:
    id: str = field(default_factory=lambda: str(uuid4()))
    document_id: str = ""
    document_title: str = ""
    source: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    relevance_scores: list[float] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    excerpt: str = ""
    url: Optional[str] = None


@dataclass
class SourceAttribution:
    claim: str
    citations: list[Citation]
    confidence: float = 1.0
    is_grounded: bool = True
    supporting_text: Optional[str] = None


@dataclass
class RetrievedContext:
    results: list[RankedResult]
    citations: list[Citation]
    graph_paths: list[GraphPath] = field(default_factory=list)
    query_time_ms: float = 0.0
    strategies_used: list[RetrievalStrategy] = field(default_factory=list)


@dataclass
class GroundednessScore:
    overall: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    faithfulness: float = 0.0
    citation_accuracy: float = 0.0


@dataclass
class GroundednessReport:
    response: str
    claims: list[SourceAttribution]
    score: GroundednessScore = field(default_factory=GroundednessScore)
    ungrounded_claims: list[str] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
