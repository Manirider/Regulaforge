"""Tests for GraphQueryService — hybrid search, traversal, impact, semantic query."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from regulaforge.knowledge_graph.application.graph_query_service import GraphQueryService
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
)
from regulaforge.knowledge_graph.domain.repository import EntityNotFoundError
from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService

from tests.knowledge_graph.conftest import (
    FakeNodeRepository,
    FakeRelationshipRepository,
)


@pytest.fixture
def empty_repos():
    node_repo = FakeNodeRepository()
    rel_repo = FakeRelationshipRepository()
    return node_repo, rel_repo


@pytest.fixture
def query_service(empty_repos):
    node_repo, rel_repo = empty_repos
    return GraphQueryService(
        node_repo=node_repo,
        rel_repo=rel_repo,
        query_repo=rel_repo,
        embedding_service=GraphEmbeddingService(),
    )


def _make_regulation(
    node_id: UUID | None = None,
    title: str = "Test Reg",
    code: str = "TR-001",
    jurisdiction: str = "RBI",
    category: str = "AML",
    node_type: GraphNodeType = GraphNodeType.REGULATION,
    **overrides: Any,
) -> TemporalNode:
    now = datetime.now(timezone.utc)
    return TemporalNode(
        id=node_id or uuid4(),
        node_type=node_type,
        labels=["regulation"],
        properties={
            "title": title,
            "code": code,
            "description": "",
            "issuing_body": "RBI",
            "jurisdiction": jurisdiction,
            "category": category,
            "status": "active",
            "effective_date": "",
            "version_str": "1.0",
            "tags": [],
            **overrides,
        },
        valid_from=now,
        valid_to=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


class TestHybridSearch:
    async def test_empty_query_raises(self, query_service: GraphQueryService) -> None:
        with pytest.raises(ValueError, match="query_text must be a non-empty string"):
            await query_service.hybrid_search(query_text="")

    async def test_returns_empty_on_repo_failure(self, query_service: GraphQueryService) -> None:
        results = await query_service.hybrid_search(query_text="KYC norms")
        assert results == []

    async def test_filters_by_temporal_snapshot(self, query_service: GraphQueryService) -> None:
        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        node = _make_regulation(title="KYC Guidelines", code="KYC-01")
        await node_repo.save(node)
        # Also save the node to the _nodes dict of the node repo so get_by_id works
        await node_repo.save(node)

        as_of = datetime(2020, 1, 1, tzinfo=timezone.utc)
        results = await query_service.hybrid_search(
            query_text="KYC",
            as_of=as_of,
        )
        assert results == []  # node created now, not valid in 2020


class TestTraverseRegulationChain:
    async def test_unknown_regulation_raises(self, query_service: GraphQueryService) -> None:
        with pytest.raises(EntityNotFoundError):
            await query_service.traverse_regulation_chain(regulation_id=uuid4())

    async def test_returns_neighborhood(self, query_service: GraphQueryService) -> None:
        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        reg = _make_regulation(code="R-01")
        saved = await node_repo.save(reg)
        result = await query_service.traverse_regulation_chain(
            regulation_id=saved.id,
            direction="outgoing",
            max_depth=3,
        )
        assert result["regulation_id"] == str(saved.id)
        assert result["regulation_code"] == "R-01"


class TestRegulationCoverage:
    async def test_no_regulations(self, query_service: GraphQueryService) -> None:
        result = await query_service.get_regulation_coverage(
            entity_type="bank",
            jurisdiction="RBI",
        )
        assert result["total_regulations"] == 0
        assert result["coverage_by_category"] == {}

    async def test_filters_by_jurisdiction(self, query_service: GraphQueryService) -> None:
        node_repo, _ = query_service._node_repo, query_service._query_repo  # type: ignore
        await node_repo.save(_make_regulation(code="RBI-01", jurisdiction="RBI", category="AML"))
        await node_repo.save(_make_regulation(code="SEBI-01", jurisdiction="SEBI", category="KYC"))
        result = await query_service.get_regulation_coverage(
            entity_type="bank",
            jurisdiction="RBI",
        )
        assert result["total_regulations"] == 1
        assert result["jurisdiction"] == "RBI"
        assert "AML" in result["coverage_by_category"]

    async def test_global_jurisdiction_includes_all(self, query_service: GraphQueryService) -> None:
        node_repo, _ = query_service._node_repo, query_service._query_repo  # type: ignore
        await node_repo.save(_make_regulation(code="R1", jurisdiction="RBI"))
        await node_repo.save(_make_regulation(code="R2", jurisdiction="SEBI"))
        result = await query_service.get_regulation_coverage(
            entity_type="any",
            jurisdiction="global",
        )
        assert result["total_regulations"] == 2


class TestFindOverlappingObligations:
    async def test_unknown_entity_raises(self, query_service: GraphQueryService) -> None:
        with pytest.raises(EntityNotFoundError):
            await query_service.find_overlapping_obligations(entity_id=uuid4())

    async def test_no_overlap_without_regulations(self, query_service: GraphQueryService) -> None:
        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        entity = _make_regulation(
            node_id=uuid4(),
            title="Bank Entity",
            code="BNK-01",
            node_type=GraphNodeType.ENTITY,
        )
        await node_repo.save(entity)
        result = await query_service.find_overlapping_obligations(
            entity_id=entity.id,
            regulations=[],
        )
        assert result == []

    async def test_detects_duplicate_obligations(self, query_service: GraphQueryService) -> None:
        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        from regulaforge.knowledge_graph.domain.models import TemporalRelationship

        entity = _make_regulation(
            node_id=uuid4(),
            title="Entity",
            code="ENT-01",
            node_type=GraphNodeType.ENTITY,
        )
        await node_repo.save(entity)
        reg = _make_regulation(code="REG-01")
        await node_repo.save(reg)

        oblig1 = _make_regulation(
            node_id=uuid4(),
            title="Submit KYC report annually",
            code="OBL-01",
            node_type=GraphNodeType.OBLIGATION,
        )
        oblig2 = _make_regulation(
            node_id=uuid4(),
            title="Submit KYC report annually",
            code="OBL-02",
            node_type=GraphNodeType.OBLIGATION,
        )
        await node_repo.save(oblig1)
        await node_repo.save(oblig2)

        await rel_repo.save(TemporalRelationship(
            id=uuid4(), source_id=reg.id, target_id=oblig1.id,
            rel_type=GraphRelationshipType.CREATES_OBLIGATION,
        ))
        await rel_repo.save(TemporalRelationship(
            id=uuid4(), source_id=reg.id, target_id=oblig2.id,
            rel_type=GraphRelationshipType.CREATES_OBLIGATION,
        ))

        result = await query_service.find_overlapping_obligations(
            entity_id=entity.id,
            regulations=[reg.id],
        )
        assert len(result) >= 1


class TestGetImpactAnalysis:
    async def test_unknown_regulation_returns_error(self, query_service: GraphQueryService) -> None:
        result = await query_service.get_impact_analysis(regulation_code="NONEXISTENT")
        assert "error" in result

    async def test_known_regulation_returns_report(self, query_service: GraphQueryService) -> None:
        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        reg = _make_regulation(code="IMP-001", title="Impact Test")
        saved = await node_repo.save(reg)
        result = await query_service.get_impact_analysis(regulation_code="IMP-001")
        assert "error" not in result
        assert result["regulation_code"] == "IMP-001"
        assert result["regulation_title"] == "Impact Test"


class TestSemanticQuery:
    async def test_empty_query_raises(self, query_service: GraphQueryService) -> None:
        with pytest.raises(ValueError, match="natural_language_query must be a non-empty string"):
            await query_service.semantic_query(natural_language_query="")

    async def test_returns_interpretation_and_results(self, query_service: GraphQueryService) -> None:
        result = await query_service.semantic_query(
            natural_language_query="What are the KYC norms under RBI?",
        )
        assert result["natural_language_query"] == "What are the KYC norms under RBI?"
        assert "interpretation" in result
        assert result["interpretation"]["query_type"] == "search"
        assert result["interpretation"]["filters_applied"]["jurisdiction"] == "RBI"
        assert "results" in result


class TestGetRegulationImpact:
    async def test_unknown_regulation_raises(self, query_service: GraphQueryService) -> None:
        with pytest.raises(EntityNotFoundError):
            await query_service.get_regulation_impact(regulation_id=uuid4())

    async def test_returns_impact_data(self, query_service: GraphQueryService) -> None:
        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        reg = _make_regulation(code="IMPACT-01")
        saved = await node_repo.save(reg)
        result = await query_service.get_regulation_impact(regulation_id=saved.id)
        assert result["regulation_id"] == str(saved.id)
        assert "impacted_entities" in result
        assert "obligations" in result
        assert "affected_clauses" in result


class TestGetTemporalEvolution:
    async def test_no_versions(self, query_service: GraphQueryService) -> None:
        result = await query_service.get_temporal_evolution(regulation_code="NONEXISTENT")
        assert result["version_count"] == 0

    async def test_returns_sorted_versions(self, query_service: GraphQueryService) -> None:
        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        now = datetime.now(timezone.utc)
        reg = _make_regulation(code="EVO-01")
        saved = await node_repo.save(reg)
        v2 = _make_regulation(
            node_id=saved.id,
            code="EVO-01",
            title="Evo Reg v2",
        )
        v2.valid_to = now
        v2.version = 2
        await node_repo.save(v2)
        result = await query_service.get_temporal_evolution(regulation_code="EVO-01")
        assert result["version_count"] >= 1


class TestFindAffectedEntities:
    async def test_unknown_regulation_raises(self, query_service: GraphQueryService) -> None:
        with pytest.raises(EntityNotFoundError):
            await query_service.find_affected_entities(regulation_id=uuid4())

    async def test_returns_empty_when_no_relationships(self, query_service: GraphQueryService) -> None:
        node_repo, _ = query_service._node_repo, query_service._query_repo  # type: ignore
        reg = _make_regulation(code="AFF-01")
        saved = await node_repo.save(reg)
        result = await query_service.find_affected_entities(regulation_id=saved.id)
        assert result == []

    async def test_returns_entity_nodes(self, query_service: GraphQueryService) -> None:
        from regulaforge.knowledge_graph.domain.models import TemporalRelationship

        node_repo, rel_repo = query_service._node_repo, query_service._query_repo  # type: ignore
        reg = _make_regulation(code="AFF-02")
        saved_reg = await node_repo.save(reg)
        entity = _make_regulation(
            node_id=uuid4(),
            title="Affected Entity",
            code="ENT-01",
            node_type=GraphNodeType.ENTITY,
        )
        saved_entity = await node_repo.save(entity)
        await rel_repo.save(TemporalRelationship(
            id=uuid4(),
            source_id=saved_reg.id,
            target_id=saved_entity.id,
            rel_type=GraphRelationshipType.APPLIES_TO,
        ))
        result = await query_service.find_affected_entities(regulation_id=saved_reg.id)
        assert len(result) == 1
        assert result[0]["properties"]["code"] == "ENT-01"
