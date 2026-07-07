"""Tests for KnowledgeGraphService."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from regulaforge.knowledge_graph.application.graph_service import KnowledgeGraphService
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
    TemporalRelationship,
)
from regulaforge.knowledge_graph.domain.repository import EntityNotFoundError
from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService

from tests.knowledge_graph.conftest import (
    FakeNodeRepository,
    FakeRelationshipRepository,
)


@pytest.fixture
def graph_service() -> KnowledgeGraphService:
    node_repo = FakeNodeRepository()
    rel_repo = FakeRelationshipRepository()
    embedding_service = GraphEmbeddingService()
    return KnowledgeGraphService(
        node_repo=node_repo,
        rel_repo=rel_repo,
        query_repo=rel_repo,
        embedding_service=embedding_service,
    )


class TestKnowledgeGraphService:
    async def test_create_regulation_node(self, graph_service: KnowledgeGraphService) -> None:
        reg_data = {
            "title": "Test Regulation",
            "code": "TR-001",
            "jurisdiction": "RBI",
            "issuing_body": "Reserve Bank",
        }
        node = await graph_service.create_regulation_node(reg_data)
        assert node.node_type == GraphNodeType.REGULATION
        assert node.properties["title"] == "Test Regulation"
        assert node.properties["code"] == "TR-001"
        assert node.version == 1

    async def test_create_regulation_node_missing_title(self, graph_service: KnowledgeGraphService) -> None:
        with pytest.raises(ValueError, match="title"):
            await graph_service.create_regulation_node({"code": "TR-001"})

    async def test_get_node_by_id(self, graph_service: KnowledgeGraphService) -> None:
        node = await graph_service.create_regulation_node({"title": "T", "code": "C"})
        retrieved = await graph_service.get_node_by_id(node.id)
        assert retrieved is not None
        assert retrieved.id == node.id

    async def test_get_node_by_id_not_found(self, graph_service: KnowledgeGraphService) -> None:
        result = await graph_service.get_node_by_id(uuid4())
        assert result is None

    async def test_link_regulation_clause(self, graph_service: KnowledgeGraphService) -> None:
        reg = await graph_service.create_regulation_node({"title": "R", "code": "R-01"})
        rel = await graph_service.link_regulation_clause(
            regulation_id=reg.id,
            clause_data={"clause_id": "C1", "title": "Clause 1", "text": "Some text"},
        )
        assert rel.rel_type == GraphRelationshipType.DERIVES_FROM
        assert rel.source_id == reg.id

    async def test_link_regulation_clause_not_found(self, graph_service: KnowledgeGraphService) -> None:
        with pytest.raises(EntityNotFoundError):
            await graph_service.link_regulation_clause(
                regulation_id=uuid4(),
                clause_data={"clause_id": "C1", "title": "Clause 1"},
            )

    async def test_update_node_properties(self, graph_service: KnowledgeGraphService) -> None:
        node = await graph_service.create_regulation_node({"title": "Old", "code": "C"})
        now = datetime.now(timezone.utc)
        updated = await graph_service.update_node_properties(
            node_id=node.id,
            properties={"title": "New Title"},
            valid_from=now + timedelta(minutes=1),
        )
        assert updated.version == 2
        assert updated.properties["title"] == "New Title"

        # Original should be closed
        history = await graph_service._node_repo.get_temporal_history(node.id)
        assert len(history) == 3
        assert history[0].version == 1 and history[0].valid_to is None  # original
        assert history[1].version == 1 and history[1].valid_to is not None  # closed
        assert history[2].version == 2 and history[2].valid_to is None  # new

    async def test_update_node_raises_if_valid_from_before(self, graph_service: KnowledgeGraphService) -> None:
        node = await graph_service.create_regulation_node({"title": "T", "code": "C"})
        with pytest.raises(ValueError, match="valid_from must be after"):
            await graph_service.update_node_properties(
                node_id=node.id,
                properties={"title": "New"},
                valid_from=datetime.now(timezone.utc) - timedelta(days=1),
            )

    async def test_merge_external_knowledge(self, graph_service: KnowledgeGraphService) -> None:
        source_data = {
            "nodes": [
                {
                    "id": str(uuid4()),
                    "node_type": "REGULATION",
                    "labels": ["imported"],
                    "properties": {"title": "Imported Reg", "code": "IR-01"},
                    "valid_from": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "relationships": [],
        }
        stats = await graph_service.merge_external_knowledge(
            source_type="test_import",
            source_data=source_data,
        )
        assert stats["nodes_created"] == 1
        assert stats["relationships_created"] == 0
        assert stats["error_count"] == 0

    async def test_save_and_get_relationship(self, graph_service: KnowledgeGraphService) -> None:
        src = await graph_service.create_regulation_node({"title": "S", "code": "S-01"})
        tgt = await graph_service.create_regulation_node({"title": "T", "code": "T-01"})
        rel = TemporalRelationship(
            id=uuid4(),
            source_id=src.id,
            target_id=tgt.id,
            rel_type=GraphRelationshipType.REFERENCES,
        )
        saved = await graph_service.save_relationship(rel)
        retrieved = await graph_service.get_relationship_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.id == saved.id

    async def test_list_nodes_by_type(self, graph_service: KnowledgeGraphService) -> None:
        await graph_service.create_regulation_node({"title": "R1", "code": "R-01"})
        await graph_service.create_regulation_node({"title": "R2", "code": "R-02"})
        nodes, total = await graph_service.list_nodes_by_type(GraphNodeType.REGULATION)
        assert total == 2
        assert len(nodes) == 2
