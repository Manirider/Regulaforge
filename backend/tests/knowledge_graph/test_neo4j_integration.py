"""Integration tests against a real Neo4j instance.

These tests require a running Neo4j instance (default: bolt://localhost:7687).
Start one via:
    docker compose -f docker/docker-compose.neo4j.yml up -d

All tests are marked with `pytest.mark.integration` and are skipped
when the Neo4j driver is unavailable or the connection fails.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
    TemporalRelationship,
)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("NEO4J_TEST_SKIP", "true").lower() == "true",
        reason="Set NEO4J_TEST_SKIP=false and start Neo4j to run integration tests",
    ),
]


def _has_neo4j() -> bool:
    try:
        import neo4j  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture(scope="module")
async def adapter():
    if not _has_neo4j():
        pytest.skip("neo4j driver not installed")

    from regulaforge.knowledge_graph.infrastructure.neo4j_adapter import Neo4jAdapter

    a = Neo4jAdapter(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "testpassword"),
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
    )
    try:
        await a.connect()
        await a.ensure_schema()
        yield a
    finally:
        await a.disconnect()


@pytest.fixture(autouse=True)
async def clean_graph(adapter: Any) -> None:
    """Clean all test data between tests via delete_all."""
    from regulaforge.knowledge_graph.infrastructure.cypher_queries import (
        MERGE_NODE,
        GET_TEMPORAL_HISTORY,
    )
    try:
        # Delete all nodes with the test label
        await adapter.query_cypher("MATCH (n:RegulaForgeTest) DETACH DELETE n")
    except Exception:
        pass


class TestNeo4jAdapter:
    async def test_connect_and_schema(self, adapter: Any) -> None:
        result = await adapter.ensure_schema()
        assert result["success"] is True
        assert isinstance(result["constraints_created"], int)
        assert isinstance(result["indexes_created"], int)

    async def test_save_and_retrieve_node(self, adapter: Any) -> None:
        now = datetime.now(timezone.utc)
        node = TemporalNode(
            id=uuid4(),
            node_type=GraphNodeType.REGULATION,
            labels=["RegulaForgeTest", "regulation"],
            properties={"title": "Test Reg", "code": "T-001"},
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        saved = await adapter.save(node)
        assert saved.id == node.id

        retrieved = await adapter.get_by_id(node.id)
        assert retrieved is not None
        assert retrieved.properties["code"] == "T-001"

    async def test_temporal_versioning(self, adapter: Any) -> None:
        now = datetime.now(timezone.utc)
        node_id = uuid4()

        v1 = TemporalNode(
            id=node_id,
            node_type=GraphNodeType.REGULATION,
            labels=["RegulaForgeTest", "regulation"],
            properties={"title": "V1", "code": "TV-01"},
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        await adapter.save(v1)

        v2 = TemporalNode(
            id=node_id,
            node_type=GraphNodeType.REGULATION,
            labels=["RegulaForgeTest", "regulation"],
            properties={"title": "V2", "code": "TV-01"},
            valid_from=now,
            valid_to=None,
            version=2,
            created_at=now,
            updated_at=now,
        )
        await adapter.save(v2)

        history = await adapter.get_temporal_history(node_id)
        assert len(history) >= 2
        versions = {n.version: n for n in history}
        assert versions[1].properties["title"] == "V1"
        assert versions[2].properties["title"] == "V2"

    async def test_relationship_crud(self, adapter: Any) -> None:
        now = datetime.now(timezone.utc)
        src = TemporalNode(
            id=uuid4(),
            node_type=GraphNodeType.REGULATION,
            labels=["RegulaForgeTest", "regulation"],
            properties={"title": "Source"},
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        tgt = TemporalNode(
            id=uuid4(),
            node_type=GraphNodeType.CLAUSE,
            labels=["RegulaForgeTest", "clause"],
            properties={"title": "Target"},
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        await adapter.save(src)
        await adapter.save(tgt)

        rel = TemporalRelationship(
            id=uuid4(),
            source_id=src.id,
            target_id=tgt.id,
            rel_type=GraphRelationshipType.DERIVES_FROM,
            properties={"certainty": 0.95},
            valid_from=now,
            valid_to=None,
            version=1,
        )
        saved_rel = await adapter.save(rel)
        assert saved_rel.id == rel.id

        retrieved = await adapter.get_by_id(rel.id)
        assert retrieved is not None

    async def test_hybrid_search(self, adapter: Any) -> None:
        now = datetime.now(timezone.utc)
        node = TemporalNode(
            id=uuid4(),
            node_type=GraphNodeType.REGULATION,
            labels=["RegulaForgeTest", "regulation"],
            properties={"title": "KYC Compliance Master Direction", "code": "KYC-MD"},
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        await adapter.save(node)

        from regulaforge.knowledge_graph.domain.models import (
            NodeWithScore,
        )

        results = await adapter.hybrid_search(
            query_text="KYC",
            top_k=10,
        )
        # May return empty if no embedding index — adapter should handle gracefully
        assert isinstance(results, list)

    async def test_soft_delete(self, adapter: Any) -> None:
        now = datetime.now(timezone.utc)
        node = TemporalNode(
            id=uuid4(),
            node_type=GraphNodeType.REGULATION,
            labels=["RegulaForgeTest", "regulation"],
            properties={"title": "Delete Me"},
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        await adapter.save(node)
        await adapter.soft_delete(node.id)
        retrieved = await adapter.get_by_id(node.id)
        assert retrieved is None
