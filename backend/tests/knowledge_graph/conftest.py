"""Shared fixtures for knowledge graph tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import pytest

from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
    TemporalRelationship,
)
from regulaforge.knowledge_graph.domain.repository import (
    GraphNodeRepository,
    GraphQueryRepository,
    GraphRelationshipRepository,
    NodeWithScore,
)


class FakeNodeRepository(GraphNodeRepository):
    """In-memory fake for testing without Neo4j."""

    def __init__(self) -> None:
        self._nodes: dict[UUID, TemporalNode] = {}
        self._history: dict[UUID, list[TemporalNode]] = {}

    async def save(self, node: TemporalNode) -> TemporalNode:
        self._nodes[node.id] = node
        if node.id not in self._history:
            self._history[node.id] = []
        self._history[node.id].append(node)
        return node

    async def get_by_id(self, node_id: UUID) -> Optional[TemporalNode]:
        node = self._nodes.get(node_id)
        return deepcopy(node) if node else None

    async def get_by_type(
        self, node_type: GraphNodeType, page: int = 1, page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        nodes = [n for n in self._nodes.values() if n.node_type == node_type]
        return nodes, len(nodes)

    async def get_by_label(
        self, label: str, page: int = 1, page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        nodes = [n for n in self._nodes.values() if label in n.labels]
        return nodes, len(nodes)

    async def search_embedding(
        self, embedding: list[float], limit: int = 20,
    ) -> list[NodeWithScore]:
        return []

    async def get_temporal_snapshot(
        self, node_id: UUID, as_of: datetime,
    ) -> Optional[TemporalNode]:
        return self._nodes.get(node_id)

    async def get_temporal_history(self, node_id: UUID) -> list[TemporalNode]:
        return self._history.get(node_id, [])

    async def soft_delete(self, node_id: UUID) -> None:
        self._nodes.pop(node_id, None)


class FakeRelationshipRepository(GraphRelationshipRepository, GraphQueryRepository):
    """In-memory fake for testing relationships and query operations."""

    def __init__(self) -> None:
        self._rels: dict[UUID, TemporalRelationship] = {}

    async def save(self, relationship: TemporalRelationship) -> TemporalRelationship:
        self._rels[relationship.id] = relationship
        return relationship

    async def get_by_id(self, rel_id: UUID) -> Optional[TemporalRelationship]:
        return self._rels.get(rel_id)

    async def get_by_source(
        self, source_id: UUID, rel_type: Optional[GraphRelationshipType] = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[TemporalRelationship], int]:
        rels = [r for r in self._rels.values() if r.source_id == source_id]
        if rel_type:
            rels = [r for r in rels if r.rel_type == rel_type]
        return rels, len(rels)

    async def get_by_target(
        self, target_id: UUID, rel_type: Optional[GraphRelationshipType] = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[TemporalRelationship], int]:
        rels = [r for r in self._rels.values() if r.target_id == target_id]
        if rel_type:
            rels = [r for r in rels if r.rel_type == rel_type]
        return rels, len(rels)

    async def get_path(
        self, source_id: UUID, target_id: UUID, max_depth: int = 5,
    ) -> list[list[TemporalRelationship]]:
        return []

    async def get_temporal_snapshot(
        self, rel_id: UUID, as_of: datetime,
    ) -> Optional[TemporalRelationship]:
        return self._rels.get(rel_id)

    async def soft_delete(self, rel_id: UUID) -> None:
        self._rels.pop(rel_id, None)

    # GraphQueryRepository implementation
    async def traverse(
        self, start_id: UUID, rel_types: Optional[list[GraphRelationshipType]] = None,
        direction: str = "outgoing", max_depth: int = 5,
    ) -> dict[str, Any]:
        return {"nodes": [], "relationships": []}

    async def hybrid_search(
        self, query_text: str, embedding: Optional[list[float]] = None,
        filters: Optional[dict[str, Any]] = None, top_k: int = 20,
    ) -> list[NodeWithScore]:
        return []

    async def get_neighborhood(
        self, node_id: UUID, depth: int = 2,
    ) -> dict[str, Any]:
        return {"nodes": [], "relationships": []}

    async def shortest_path(
        self, source_id: UUID, target_id: UUID,
        rel_types: Optional[list[GraphRelationshipType]] = None,
    ) -> Optional[dict[str, Any]]:
        return None

    async def query_cypher(
        self, cypher_query: str, **params: Any,
    ) -> list[dict[str, Any]]:
        return []


@pytest.fixture
def fake_node_repo() -> FakeNodeRepository:
    return FakeNodeRepository()


@pytest.fixture
def fake_rel_repo() -> FakeRelationshipRepository:
    return FakeRelationshipRepository()
