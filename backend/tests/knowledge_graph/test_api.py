"""API-level integration tests for the Knowledge Graph router.

Uses FastAPI TestClient with dependency overrides to bypass Neo4j and auth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from regulaforge.knowledge_graph.application.graph_query_service import GraphQueryService
from regulaforge.knowledge_graph.application.graph_service import KnowledgeGraphService
from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService

from tests.knowledge_graph.conftest import (
    FakeNodeRepository,
    FakeRelationshipRepository,
)


@pytest.fixture
def fake_node_repo() -> FakeNodeRepository:
    return FakeNodeRepository()


@pytest.fixture
def fake_rel_repo() -> FakeRelationshipRepository:
    return FakeRelationshipRepository()


@pytest.fixture
def graph_service(
    fake_node_repo: FakeNodeRepository,
    fake_rel_repo: FakeRelationshipRepository,
) -> KnowledgeGraphService:
    return KnowledgeGraphService(
        node_repo=fake_node_repo,
        rel_repo=fake_rel_repo,
        query_repo=fake_rel_repo,
        embedding_service=GraphEmbeddingService(),
    )


@pytest.fixture
def query_service(
    fake_node_repo: FakeNodeRepository,
    fake_rel_repo: FakeRelationshipRepository,
) -> GraphQueryService:
    return GraphQueryService(
        node_repo=fake_node_repo,
        rel_repo=fake_rel_repo,
        query_repo=fake_rel_repo,
        embedding_service=GraphEmbeddingService(),
    )


@pytest.fixture
def app(
    graph_service: KnowledgeGraphService,
    query_service: GraphQueryService,
) -> FastAPI:
    from regulaforge.knowledge_graph.interfaces.api import router as kg_router
    from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user

    app = FastAPI(lifespan=None)

    # Override auth to return a test user
    async def _mock_get_current_user() -> dict[str, Any]:
        return {
            "user_id": str(uuid4()),
            "username": "testuser",
            "roles": ["admin"],
        }

    # Override services with fake-based instances
    app.dependency_overrides[get_current_user] = _mock_get_current_user

    # We override the functions, not the classes
    from regulaforge.knowledge_graph.interfaces import api as kg_api_module

    original_get_graph = kg_api_module.get_graph_service
    original_get_query = kg_api_module.get_query_service
    original_get_embedding = kg_api_module.get_embedding_service
    original_get_adapter = kg_api_module.get_neo4j_adapter

    async def _fake_get_graph_service() -> KnowledgeGraphService:
        return graph_service

    async def _fake_get_query_service() -> GraphQueryService:
        return query_service

    async def _fake_get_embedding() -> GraphEmbeddingService:
        return GraphEmbeddingService()

    app.dependency_overrides[original_get_graph] = _fake_get_graph_service
    app.dependency_overrides[original_get_query] = _fake_get_query_service
    app.dependency_overrides[original_get_embedding] = _fake_get_embedding

    # Override neo4j adapter to prevent connection attempts
    async def _fake_get_adapter() -> Any:
        return fake_node_repo  # FakeNodeRepo implements all three interfaces

    app.dependency_overrides[original_get_adapter] = _fake_get_adapter

    app.include_router(kg_router, prefix="/api/v1")
    return app


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestNodeAPI:
    async def test_create_node(
        self, async_client: AsyncClient,
    ) -> None:
        payload = {
            "node_type": "REGULATION",
            "labels": ["regulation"],
            "properties": {"title": "Test Reg", "code": "TR-001"},
        }
        resp = await async_client.post("/api/v1/knowledge-graph/nodes", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["node_type"] == "REGULATION"
        assert data["properties"]["title"] == "Test Reg"

    async def test_create_node_invalid_type(
        self, async_client: AsyncClient,
    ) -> None:
        payload = {
            "node_type": "INVALID_TYPE",
            "labels": [],
            "properties": {"title": "Bad"},
        }
        resp = await async_client.post("/api/v1/knowledge-graph/nodes", json=payload)
        # Pydantic field validation returns 422 for invalid enum values
        assert resp.status_code == 422

    async def test_get_node(
        self, async_client: AsyncClient,
    ) -> None:
        create_payload = {
            "node_type": "REGULATION",
            "labels": [],
            "properties": {"title": "Get Me", "code": "G-01"},
        }
        create_resp = await async_client.post(
            "/api/v1/knowledge-graph/nodes", json=create_payload,
        )
        node_id = create_resp.json()["id"]

        resp = await async_client.get(f"/api/v1/knowledge-graph/nodes/{node_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == node_id

    async def test_get_node_not_found(
        self, async_client: AsyncClient,
    ) -> None:
        resp = await async_client.get(
            f"/api/v1/knowledge-graph/nodes/{uuid4()}",
        )
        assert resp.status_code == 404

    async def test_list_nodes(
        self, async_client: AsyncClient,
    ) -> None:
        payload = {
            "node_type": "REGULATION",
            "labels": [],
            "properties": {"title": "List Me", "code": "L-01"},
        }
        await async_client.post("/api/v1/knowledge-graph/nodes", json=payload)
        await async_client.post("/api/v1/knowledge-graph/nodes", json={
            **payload, "properties": {"title": "List Me 2", "code": "L-02"},
        })

        resp = await async_client.get(
            "/api/v1/knowledge-graph/nodes?node_type=REGULATION",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2


class TestRelationshipAPI:
    async def test_create_relationship(
        self, async_client: AsyncClient,
    ) -> None:
        src_resp = await async_client.post("/api/v1/knowledge-graph/nodes", json={
            "node_type": "REGULATION", "labels": [], "properties": {"title": "Src", "code": "S-01"},
        })
        tgt_resp = await async_client.post("/api/v1/knowledge-graph/nodes", json={
            "node_type": "CLAUSE", "labels": [], "properties": {"title": "Tgt", "clause_id": "C-01"},
        })
        src_id = src_resp.json()["id"]
        tgt_id = tgt_resp.json()["id"]

        payload = {
            "source_id": src_id,
            "target_id": tgt_id,
            "rel_type": "DERIVES_FROM",
            "properties": {"certainty": 0.95},
        }
        resp = await async_client.post(
            "/api/v1/knowledge-graph/relationships", json=payload,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["rel_type"] == "DERIVES_FROM"

    async def test_get_relationship_not_found(
        self, async_client: AsyncClient,
    ) -> None:
        resp = await async_client.get(
            f"/api/v1/knowledge-graph/relationships/{uuid4()}",
        )
        assert resp.status_code == 404


class TestQueryAPI:
    async def test_hybrid_search(
        self, async_client: AsyncClient,
    ) -> None:
        resp = await async_client.post("/api/v1/knowledge-graph/query/hybrid", json={
            "query_text": "KYC compliance",
            "top_k": 10,
        })
        assert resp.status_code == 200
        assert "results" in resp.json()

    async def test_traverse(
        self, async_client: AsyncClient,
    ) -> None:
        payload = {
            "start_id": str(uuid4()),
            "direction": "outgoing",
            "max_depth": 3,
        }
        resp = await async_client.post(
            "/api/v1/knowledge-graph/query/traverse", json=payload,
        )
        # Traverse on non-existent node returns error gracefully
        assert resp.status_code in (200, 404)

    async def test_impact_analysis(
        self, async_client: AsyncClient,
    ) -> None:
        resp = await async_client.get(
            "/api/v1/knowledge-graph/impact/NONEXISTENT",
        )
        assert resp.status_code in (200, 404)

    async def test_semantic_query(
        self, async_client: AsyncClient,
    ) -> None:
        resp = await async_client.post("/api/v1/knowledge-graph/query/semantic", json={
            "query": "What are the KYC norms under RBI?",
        })
        assert resp.status_code in (200, 422)


class TestComplianceAPI:
    async def test_get_compliance_obligations_not_found(
        self, async_client: AsyncClient,
    ) -> None:
        resp = await async_client.get(
            f"/api/v1/knowledge-graph/obligations/{uuid4()}",
        )
        assert resp.status_code == 404

    async def test_merge_external_knowledge(
        self, async_client: AsyncClient,
    ) -> None:
        payload = {
            "source_type": "test_import",
            "nodes": [
                {
                    "id": str(uuid4()),
                    "node_type": "REGULATION",
                    "labels": ["imported"],
                    "properties": {"title": "Imported", "code": "IMP-01"},
                    "valid_from": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "relationships": [],
        }
        resp = await async_client.post(
            "/api/v1/knowledge-graph/merge", json=payload,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["nodes_created"] == 1


class TestCompareAPI:
    async def test_compare_versions_not_found(
        self, async_client: AsyncClient,
    ) -> None:
        resp = await async_client.get(
            f"/api/v1/knowledge-graph/compare/{uuid4()}?version_a=1&version_b=2",
        )
        assert resp.status_code == 404
