"""Tests for knowledge graph domain models."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import pytest

from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    GraphPath,
    GraphQuery,
    TemporalNode,
    TemporalRelationship,
)


class TestGraphNodeType:
    def test_values(self) -> None:
        assert GraphNodeType.REGULATION.value == "REGULATION"
        assert GraphNodeType.CLAUSE.value == "CLAUSE"
        assert GraphNodeType.OBLIGATION.value == "OBLIGATION"
        assert GraphNodeType.ENTITY.value == "ENTITY"

    def test_from_string(self) -> None:
        assert GraphNodeType("REGULATION") == GraphNodeType.REGULATION
        with pytest.raises(ValueError):
            GraphNodeType("INVALID_TYPE")


class TestGraphRelationshipType:
    def test_values(self) -> None:
        assert GraphRelationshipType.AMENDS.value == "AMENDS"
        assert GraphRelationshipType.SUPERSEDES.value == "SUPERSEDES"
        assert GraphRelationshipType.REFERENCES.value == "REFERENCES"
        assert GraphRelationshipType.DERIVES_FROM.value == "DERIVES_FROM"

    def test_from_string(self) -> None:
        assert GraphRelationshipType("AMENDS") == GraphRelationshipType.AMENDS
        with pytest.raises(ValueError):
            GraphRelationshipType("INVALID_TYPE")


class TestTemporalNode:
    def test_minimal_creation(self) -> None:
        node = TemporalNode(id=uuid4(), node_type=GraphNodeType.REGULATION)
        assert node.id is not None
        assert node.node_type == GraphNodeType.REGULATION
        assert node.labels == []
        assert node.properties == {}
        assert node.version == 1
        assert node.embedding is None

    def test_validation_id_must_be_uuid(self) -> None:
        with pytest.raises(ValueError, match="id must be a UUID"):
            TemporalNode(id="not-a-uuid", node_type=GraphNodeType.REGULATION)  # type: ignore[arg-type]

    def test_validation_node_type_must_be_enum(self) -> None:
        with pytest.raises(ValueError, match="node_type must be a GraphNodeType"):
            TemporalNode(id=uuid4(), node_type="INVALID")  # type: ignore[arg-type]

    def test_validation_version_must_be_positive(self) -> None:
        node_id = uuid4()
        TemporalNode(id=node_id, node_type=GraphNodeType.CLAUSE, version=1)
        with pytest.raises(ValueError, match="version must be >= 1"):
            TemporalNode(id=node_id, node_type=GraphNodeType.CLAUSE, version=0)

    def test_validation_valid_to_after_valid_from(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="valid_to must be after valid_from"):
            TemporalNode(
                id=uuid4(),
                node_type=GraphNodeType.REGULATION,
                valid_from=now,
                valid_to=now - timedelta(hours=1),
            )

    def test_is_valid_at(self) -> None:
        now = datetime.now(timezone.utc)
        node = TemporalNode(
            id=uuid4(),
            node_type=GraphNodeType.REGULATION,
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=1),
        )
        assert node.is_valid_at(now)
        assert node.is_valid_at(now - timedelta(hours=12))
        assert not node.is_valid_at(now - timedelta(days=2))
        assert not node.is_valid_at(now + timedelta(days=2))

    def test_is_valid_at_no_end(self) -> None:
        now = datetime.now(timezone.utc)
        node = TemporalNode(
            id=uuid4(),
            node_type=GraphNodeType.REGULATION,
            valid_from=now - timedelta(days=1),
            valid_to=None,
        )
        assert node.is_valid_at(now)
        assert node.is_valid_at(now + timedelta(days=365))

    def test_to_dict(self) -> None:
        node_id = uuid4()
        now = datetime.now(timezone.utc)
        node = TemporalNode(
            id=node_id,
            node_type=GraphNodeType.REGULATION,
            labels=["regulation", "rbi"],
            properties={"title": "Test Reg", "code": "TR-01"},
            valid_from=now,
            valid_to=None,
            version=2,
            created_at=now,
            updated_at=now,
        )
        d = node.to_dict()
        assert d["id"] == str(node_id)
        assert d["node_type"] == "REGULATION"
        assert d["labels"] == ["regulation", "rbi"]
        assert d["properties"]["title"] == "Test Reg"
        assert d["version"] == 2
        assert d["valid_to"] is None


class TestTemporalRelationship:
    def test_minimal_creation(self) -> None:
        rel = TemporalRelationship(
            id=uuid4(),
            source_id=uuid4(),
            target_id=uuid4(),
            rel_type=GraphRelationshipType.REFERENCES,
        )
        assert rel.rel_type == GraphRelationshipType.REFERENCES
        assert rel.properties == {}
        assert rel.version == 1

    def test_validation_source_target_uuid(self) -> None:
        with pytest.raises(ValueError, match="source_id must be a UUID"):
            TemporalRelationship(
                id=uuid4(),
                source_id="not-uuid",
                target_id=uuid4(),
                rel_type=GraphRelationshipType.AMENDS,
            )

    def test_validation_rel_type_must_be_enum(self) -> None:
        with pytest.raises(ValueError, match="rel_type must be a GraphRelationshipType"):
            TemporalRelationship(
                id=uuid4(),
                source_id=uuid4(),
                target_id=uuid4(),
                rel_type="INVALID",
            )

    def test_is_valid_at(self) -> None:
        now = datetime.now(timezone.utc)
        rel = TemporalRelationship(
            id=uuid4(),
            source_id=uuid4(),
            target_id=uuid4(),
            rel_type=GraphRelationshipType.APPLIES_TO,
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=1),
        )
        assert rel.is_valid_at(now)
        assert not rel.is_valid_at(now + timedelta(days=2))

    def test_to_dict(self) -> None:
        rel_id = uuid4()
        src_id = uuid4()
        tgt_id = uuid4()
        rel = TemporalRelationship(
            id=rel_id,
            source_id=src_id,
            target_id=tgt_id,
            rel_type=GraphRelationshipType.DERIVES_FROM,
            properties={"context": "main clause"},
        )
        d = rel.to_dict()
        assert d["id"] == str(rel_id)
        assert d["source_id"] == str(src_id)
        assert d["target_id"] == str(tgt_id)
        assert d["rel_type"] == "DERIVES_FROM"
        assert d["properties"]["context"] == "main clause"


class TestGraphQuery:
    def test_creation(self) -> None:
        q = GraphQuery(query_type="search", limit=10)
        assert q.query_type == "search"
        assert q.limit == 10
        assert q.offset == 0

    def test_validation_limit(self) -> None:
        with pytest.raises(ValueError, match="limit must be >= 1"):
            GraphQuery(query_type="search", limit=0)

    def test_validation_offset(self) -> None:
        with pytest.raises(ValueError, match="offset must be >= 0"):
            GraphQuery(query_type="search", offset=-1)


class TestGraphPath:
    def test_creation(self) -> None:
        path = GraphPath(score=0.95)
        assert path.nodes == []
        assert path.relationships == []
        assert path.score == 0.95

    def test_to_dict(self) -> None:
        node = TemporalNode(id=uuid4(), node_type=GraphNodeType.REGULATION)
        rel = TemporalRelationship(
            id=uuid4(), source_id=uuid4(), target_id=uuid4(),
            rel_type=GraphRelationshipType.REFERENCES,
        )
        path = GraphPath(nodes=[node], relationships=[rel], score=1.0)
        d = path.to_dict()
        assert len(d["nodes"]) == 1
        assert len(d["relationships"]) == 1
        assert d["score"] == 1.0
