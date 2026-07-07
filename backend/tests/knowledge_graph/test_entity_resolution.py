"""Tests for entity resolution service."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from regulaforge.knowledge_graph.application.entity_resolution import (
    EntityResolutionService,
    ResolutionCandidate,
    MergeResult,
)
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    TemporalNode,
    TemporalRelationship,
    GraphRelationshipType,
)
from regulaforge.knowledge_graph.domain.repository import EntityNotFoundError

from tests.knowledge_graph.conftest import (
    FakeNodeRepository,
    FakeRelationshipRepository,
)


@pytest.fixture
def node_repo() -> FakeNodeRepository:
    return FakeNodeRepository()


@pytest.fixture
def rel_repo() -> FakeRelationshipRepository:
    return FakeRelationshipRepository()


@pytest.fixture
def resolution_service(
    node_repo: FakeNodeRepository,
    rel_repo: FakeRelationshipRepository,
) -> EntityResolutionService:
    return EntityResolutionService(node_repo=node_repo, rel_repo=rel_repo, threshold=0.5)


class TestResolutionCandidate:
    def test_creation(self) -> None:
        n1 = TemporalNode(id=uuid4(), node_type=GraphNodeType.REGULATION)
        n2 = TemporalNode(id=uuid4(), node_type=GraphNodeType.REGULATION)
        cand = ResolutionCandidate(source=n1, target=n2, similarity_score=0.95, match_fields=["title"])
        assert cand.source.id == n1.id
        assert cand.target.id == n2.id
        assert cand.similarity_score == 0.95
        assert cand.match_fields == ["title"]


class TestMergeResult:
    def test_creation(self) -> None:
        sid = uuid4()
        mid = uuid4()
        result = MergeResult(
            surviving_node_id=sid,
            merged_node_id=mid,
            merged_properties={"title": "Test"},
            merged_labels=["label1"],
            conflict_count=0,
            merged_relationship_count=3,
        )
        assert result.surviving_node_id == sid
        assert result.merged_node_id == mid
        assert result.conflict_count == 0
        assert result.merged_relationship_count == 3


class TestEntityResolutionService:
    async def test_find_duplicates_empty(self, resolution_service: EntityResolutionService) -> None:
        candidates = await resolution_service.find_duplicates()
        assert candidates == []

    async def test_find_duplicates_exact_match(
        self,
        node_repo: FakeNodeRepository,
        resolution_service: EntityResolutionService,
    ) -> None:
        n1 = TemporalNode(
            id=uuid4(), node_type=GraphNodeType.REGULATION,
            properties={"title": "GDPR Regulation", "code": "GDPR"},
        )
        n2 = TemporalNode(
            id=uuid4(), node_type=GraphNodeType.REGULATION,
            properties={"title": "GDPR Regulation", "code": "GDPR-EU"},
        )
        await node_repo.save(n1)
        await node_repo.save(n2)

        candidates = await resolution_service.find_duplicates()
        assert len(candidates) >= 1
        assert candidates[0].similarity_score >= 0.5

    async def test_find_duplicates_no_match(
        self,
        node_repo: FakeNodeRepository,
        resolution_service: EntityResolutionService,
    ) -> None:
        n1 = TemporalNode(
            id=uuid4(), node_type=GraphNodeType.REGULATION,
            properties={"title": "GDPR Regulation", "code": "GDPR"},
        )
        n2 = TemporalNode(
            id=uuid4(), node_type=GraphNodeType.REGULATION,
            properties={"title": "PCI DSS Standard", "code": "PCI-DSS"},
        )
        await node_repo.save(n1)
        await node_repo.save(n2)

        # With high threshold they should not match
        svc = EntityResolutionService(node_repo=node_repo, rel_repo=FakeRelationshipRepository(), threshold=0.95)
        candidates = await svc.find_duplicates()
        assert candidates == []

    async def test_merge_nodes(
        self,
        node_repo: FakeNodeRepository,
        rel_repo: FakeRelationshipRepository,
        resolution_service: EntityResolutionService,
    ) -> None:
        sid = uuid4()
        tid = uuid4()
        source = TemporalNode(
            id=sid, node_type=GraphNodeType.REGULATION,
            properties={"title": "GDPR", "code": "GDPR-EU"},
        )
        target = TemporalNode(
            id=tid, node_type=GraphNodeType.REGULATION,
            properties={"title": "General Data Protection Regulation", "code": "GDPR"},
        )
        await node_repo.save(source)
        await node_repo.save(target)

        rel = TemporalRelationship(
            id=uuid4(), source_id=sid, target_id=tid,
            rel_type=GraphRelationshipType.REFERENCES,
        )
        await rel_repo.save(rel)

        result = await resolution_service.merge_nodes(source_id=sid, target_id=tid, source_priority=True)
        assert result.surviving_node_id == sid
        assert result.merged_node_id == tid
        assert result.conflict_count >= 0

    async def test_merge_nodes_different_types_raises(
        self,
        node_repo: FakeNodeRepository,
        resolution_service: EntityResolutionService,
    ) -> None:
        sid = uuid4()
        tid = uuid4()
        source = TemporalNode(id=sid, node_type=GraphNodeType.REGULATION)
        target = TemporalNode(id=tid, node_type=GraphNodeType.CLAUSE)
        await node_repo.save(source)
        await node_repo.save(target)

        with pytest.raises(ValueError, match="Cannot merge nodes of different types"):
            await resolution_service.merge_nodes(source_id=sid, target_id=tid)

    async def test_merge_nodes_not_found(
        self,
        resolution_service: EntityResolutionService,
    ) -> None:
        with pytest.raises(EntityNotFoundError):
            await resolution_service.merge_nodes(source_id=uuid4(), target_id=uuid4())

    async def test_text_similarity(self, resolution_service: EntityResolutionService) -> None:
        sim = resolution_service._text_similarity("GDPR Regulation", "GDPR Regulation")
        assert sim == 1.0

        sim = resolution_service._text_similarity("GDPR", "PCI-DSS")
        assert sim < 0.5

        sim = resolution_service._text_similarity("", "test")
        assert sim == 0.0

        sim = resolution_service._text_similarity("Same Text", "same text")
        assert sim == 1.0
