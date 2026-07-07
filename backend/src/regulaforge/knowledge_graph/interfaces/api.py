"""Knowledge Graph API endpoints.

Exposes temporal knowledge graph operations as RESTful endpoints.
No business logic — delegates all operations to application services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from regulaforge.config.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
    MAX_PAGE_SIZE,
)
from regulaforge.knowledge_graph.domain.repository import EntityNotFoundError
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user
from regulaforge.knowledge_graph.application.graph_query_service import GraphQueryService
from regulaforge.knowledge_graph.application.graph_service import KnowledgeGraphService
from regulaforge.knowledge_graph.domain.models import GraphNodeType, TemporalNode
from regulaforge.knowledge_graph.domain.repository import RepositoryError

router = APIRouter(
    prefix="/knowledge-graph",
    tags=["Knowledge Graph"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field, field_validator  # noqa: E402


class NodeCreateRequest(BaseModel):
    """Request schema for creating a graph node."""

    node_type: str = Field(..., description="GraphNodeType value (e.g. REGULATION, CLAUSE)")
    labels: list[str] = Field(default=[], description="Node labels")
    properties: dict[str, Any] = Field(..., description="Node properties")
    valid_from: Optional[str] = Field(default=None, description="ISO 8601 datetime string")

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        valid = {t.value for t in GraphNodeType}
        if v.upper() not in valid:
            raise ValueError(f"node_type must be one of {valid}")
        return v.upper()


class NodeResponse(BaseModel):
    """Response schema for a graph node."""

    id: str
    node_type: str
    labels: list[str]
    properties: dict[str, Any]
    valid_from: str
    valid_to: Optional[str] = None
    version: int
    created_at: str
    updated_at: str
    embedding: Optional[list[float]] = None


class RelationshipCreateRequest(BaseModel):
    """Request schema for creating a graph relationship."""

    source_id: str = Field(..., description="Source node UUID")
    target_id: str = Field(..., description="Target node UUID")
    rel_type: str = Field(..., description="GraphRelationshipType value")
    properties: dict[str, Any] = Field(default={}, description="Relationship properties")
    valid_from: Optional[str] = Field(default=None, description="ISO 8601 datetime string")

    @field_validator("rel_type")
    @classmethod
    def validate_rel_type(cls, v: str) -> str:
        from regulaforge.knowledge_graph.domain.models import GraphRelationshipType
        valid = {t.value for t in GraphRelationshipType}
        if v.upper() not in valid:
            raise ValueError(f"rel_type must be one of {valid}")
        return v.upper()


class RelationshipResponse(BaseModel):
    """Response schema for a graph relationship."""

    id: str
    source_id: str
    target_id: str
    rel_type: str
    properties: dict[str, Any]
    valid_from: str
    valid_to: Optional[str] = None
    version: int
    created_at: str
    updated_at: str


class HybridSearchRequest(BaseModel):
    """Request schema for hybrid search."""

    query_text: str = Field(..., min_length=1, description="Search query text")
    filters: Optional[dict[str, Any]] = Field(default=None, description="Search filters")
    top_k: int = Field(default=20, ge=1, le=100, description="Maximum results")
    as_of: Optional[str] = Field(default=None, description="Temporal point-in-time (ISO 8601)")


class TraverseRequest(BaseModel):
    """Request schema for graph traversal."""

    start_id: str = Field(..., description="Starting node UUID")
    rel_types: Optional[list[str]] = Field(default=None, description="Relationship types to follow")
    direction: str = Field(default="outgoing", description="outgoing, incoming, or both")
    max_depth: int = Field(default=5, ge=1, le=20, description="Maximum traversal depth")


class MergeRequest(BaseModel):
    """Request schema for merging external knowledge."""

    source_type: str = Field(..., min_length=1, description="Source identifier")
    nodes: list[dict[str, Any]] = Field(..., description="List of node data")
    relationships: list[dict[str, Any]] = Field(default=[], description="List of relationship data")


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Singleton adapter — initialized once at application startup
# ---------------------------------------------------------------------------

_neo4j_adapter: Any = None


async def get_neo4j_adapter() -> Any:
    """Return the singleton Neo4j adapter instance."""
    global _neo4j_adapter
    if _neo4j_adapter is None:
        from regulaforge.knowledge_graph.infrastructure.neo4j_adapter import Neo4jAdapter
        _neo4j_adapter = Neo4jAdapter()
        await _neo4j_adapter.connect()
    return _neo4j_adapter


async def get_embedding_service() -> Any:
    """Create a GraphEmbeddingService instance."""
    from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService
    return GraphEmbeddingService()


async def get_graph_service(
    neo4j: Any = Depends(get_neo4j_adapter),  # noqa: B008
    embedding_service: Any = Depends(get_embedding_service),  # noqa: B008
) -> KnowledgeGraphService:
    """Get the KnowledgeGraphService instance with injected dependencies."""
    return KnowledgeGraphService(
        node_repo=neo4j,
        rel_repo=neo4j,
        query_repo=neo4j,
        embedding_service=embedding_service,
    )


async def get_query_service(
    neo4j: Any = Depends(get_neo4j_adapter),  # noqa: B008
    embedding_service: Any = Depends(get_embedding_service),  # noqa: B008
) -> GraphQueryService:
    """Get the GraphQueryService instance with injected dependencies."""
    return GraphQueryService(
        node_repo=neo4j,
        rel_repo=neo4j,
        query_repo=neo4j,
        embedding_service=embedding_service,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/nodes", response_model=NodeResponse, status_code=HTTP_201_CREATED)
async def create_node(
    request: NodeCreateRequest,
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Create a new node in the knowledge graph."""
    try:
        node_type = GraphNodeType(request.node_type)
        now = datetime.now(timezone.utc)

        valid_from = datetime.fromisoformat(request.valid_from) if request.valid_from else now

        node = TemporalNode(
            id=uuid4(),
            node_type=node_type,
            labels=request.labels,
            properties=request.properties,
            valid_from=valid_from,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )

        if node_type == GraphNodeType.REGULATION:
            saved = await service.create_regulation_node(request.properties)
        else:
            saved = await service.save_node(node)

        return _node_to_response(saved)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except RepositoryError as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: UUID,
    as_of: Optional[str] = Query(default=None, description="ISO 8601 point-in-time"),
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Get a graph node by ID, optionally at a point in time."""
    try:
        as_of_dt = datetime.fromisoformat(as_of) if as_of else None
        node = await service.get_node_by_id(node_id, as_of=as_of_dt)

        if not node:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Node '{node_id}' not found",
            )
        return _node_to_response(node)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except RepositoryError as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/nodes", response_model=PaginatedResponse)
async def list_nodes(
    node_type: Optional[str] = Query(default=None, description="Filter by node type"),
    label: Optional[str] = Query(default=None, description="Filter by label"),
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Search or list nodes with filtering and pagination."""
    try:
        if node_type:
            nt = GraphNodeType(node_type.upper())
            nodes, total = await service.list_nodes_by_type(nt, page=page, page_size=page_size)
        elif label:
            nodes, total = await service.list_nodes_by_label(label, page=page, page_size=page_size)
        else:
            nodes, total = await service.list_nodes_by_type(
                GraphNodeType.REGULATION, page=page, page_size=page_size,
            )

        total_pages = max(1, -(-total // page_size))

        return PaginatedResponse(
            items=[_node_to_response(n) for n in nodes],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except RepositoryError as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/relationships", response_model=RelationshipResponse, status_code=HTTP_201_CREATED)
async def create_relationship(
    request: RelationshipCreateRequest,
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Create a new relationship between two graph nodes."""
    try:
        from uuid import uuid4

        from regulaforge.knowledge_graph.domain.models import GraphRelationshipType, TemporalRelationship

        rel_type = GraphRelationshipType(request.rel_type)
        now = datetime.now()

        valid_from = datetime.fromisoformat(request.valid_from) if request.valid_from else now

        relationship = TemporalRelationship(
            id=uuid4(),
            source_id=UUID(request.source_id),
            target_id=UUID(request.target_id),
            rel_type=rel_type,
            properties=request.properties,
            valid_from=valid_from,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )

        saved = await service.save_relationship(relationship)
        return _relationship_to_response(saved)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except RepositoryError as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/relationships/{rel_id}", response_model=RelationshipResponse)
async def get_relationship(
    rel_id: UUID,
    as_of: Optional[str] = Query(default=None, description="ISO 8601 point-in-time"),
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Get a relationship by ID, optionally at a point in time."""
    try:
        as_of_dt = datetime.fromisoformat(as_of) if as_of else None
        rel = await service.get_relationship_by_id(rel_id, as_of=as_of_dt)

        if not rel:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Relationship '{rel_id}' not found",
            )
        return _relationship_to_response(rel)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except RepositoryError as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/query/hybrid")
async def hybrid_search(
    request: HybridSearchRequest,
    query_service: GraphQueryService = Depends(get_query_service),  # noqa: B008
) -> Any:
    """Perform hybrid search (text + vector) against the knowledge graph."""
    try:
        as_of = datetime.fromisoformat(request.as_of) if request.as_of else None

        results = await query_service.hybrid_search(
            query_text=request.query_text,
            filters=request.filters,
            top_k=request.top_k,
            as_of=as_of,
        )

        return {
            "query": request.query_text,
            "total_results": len(results),
            "results": results,
        }
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/query/traverse")
async def traverse_graph(
    request: TraverseRequest,
    query_service: GraphQueryService = Depends(get_query_service),  # noqa: B008
) -> Any:
    """Traverse the graph from a starting node."""
    try:
        from regulaforge.knowledge_graph.domain.models import GraphRelationshipType

        if request.rel_types:
            [GraphRelationshipType(rt.upper()) for rt in request.rel_types]

        result = await query_service.traverse_regulation_chain(
            regulation_id=UUID(request.start_id),
            direction=request.direction,
            max_depth=request.max_depth,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/impact/{regulation_id}")
async def get_impact_analysis(
    regulation_id: str,
    query_service: GraphQueryService = Depends(get_query_service),  # noqa: B008
) -> Any:
    """Get full impact analysis for a regulation.

    Accepts either a regulation UUID or regulation code (e.g., 'RBI-MASTER-2024').
    """
    try:
        impact = await query_service.get_impact_analysis(
            regulation_code=regulation_id,
        )
        return impact
    except EntityNotFoundError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/obligations/{entity_id}")
async def get_compliance_obligations(
    entity_id: UUID,
    as_of: Optional[str] = Query(default=None, description="ISO 8601 point-in-time"),
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Get all compliance obligations for an entity at a point in time."""
    try:
        as_of_dt = datetime.fromisoformat(as_of) if as_of else None
        obligations = await service.get_compliance_obligations(
            entity_id=entity_id,
            as_of=as_of_dt,
        )
        return {
            "entity_id": str(entity_id),
            "as_of": (as_of_dt or datetime.now()).isoformat(),
            "obligations": obligations,
            "total": len(obligations),
        }
    except EntityNotFoundError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/merge")
async def merge_external_knowledge(
    request: MergeRequest,
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Merge external knowledge into the knowledge graph."""
    try:
        source_data = {
            "nodes": request.nodes,
            "relationships": request.relationships,
        }
        stats = await service.merge_external_knowledge(
            source_type=request.source_type,
            source_data=source_data,
        )
        return stats
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/query/semantic")
async def semantic_query(
    request: HybridSearchRequest,
    query_service: GraphQueryService = Depends(get_query_service),  # noqa: B008
) -> Any:
    """Execute a natural language semantic query against the knowledge graph."""
    try:
        result = await query_service.semantic_query(
            natural_language_query=request.query_text,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Version Comparison
# ---------------------------------------------------------------------------


class VersionCompareRequest(BaseModel):
    """Request schema for comparing two versions of a node."""

    node_id: str = Field(..., description="UUID of the node")
    version_a: int = Field(..., description="First version number")
    version_b: int = Field(..., description="Second version number")

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, v: str) -> str:
        UUID(v)
        return v


@router.get("/compare/{node_id}")
async def compare_node_versions(
    node_id: UUID,
    version_a: int = Query(..., description="First version to compare"),
    version_b: int = Query(..., description="Second version to compare"),
    service: KnowledgeGraphService = Depends(get_graph_service),  # noqa: B008
) -> Any:
    """Compare two versions of a node and return the diff.

    Delegates all business logic to KnowledgeGraphService.compare_versions().
    """
    try:
        result = await service.compare_versions(
            node_id=node_id,
            version_a=version_a,
            version_b=version_b,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _node_to_response(node: Any) -> dict[str, Any]:
    """Convert a TemporalNode to API response dict."""
    data = node.to_dict() if hasattr(node, "to_dict") else node
    if isinstance(data, dict):
        return {
            "id": data.get("id", ""),
            "node_type": data.get("node_type", ""),
            "labels": data.get("labels", []),
            "properties": data.get("properties", {}),
            "valid_from": data.get("valid_from", ""),
            "valid_to": data.get("valid_to"),
            "version": data.get("version", 1),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "embedding": data.get("embedding"),
        }
    return NodeResponse(
        id=str(node.id),
        node_type=node.node_type.value,
        labels=node.labels,
        properties=node.properties,
        valid_from=node.valid_from.isoformat(),
        valid_to=node.valid_to.isoformat() if node.valid_to else None,
        version=node.version,
        created_at=node.created_at.isoformat(),
        updated_at=node.updated_at.isoformat(),
        embedding=node.embedding,
    )


def _relationship_to_response(rel: Any) -> dict[str, Any]:
    """Convert a TemporalRelationship to API response dict."""
    data = rel.to_dict() if hasattr(rel, "to_dict") else rel
    if isinstance(data, dict):
        return {
            "id": data.get("id", ""),
            "source_id": data.get("source_id", ""),
            "target_id": data.get("target_id", ""),
            "rel_type": data.get("rel_type", ""),
            "properties": data.get("properties", {}),
            "valid_from": data.get("valid_from", ""),
            "valid_to": data.get("valid_to"),
            "version": data.get("version", 1),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
        }
    return RelationshipResponse(
        id=str(rel.id),
        source_id=str(rel.source_id),
        target_id=str(rel.target_id),
        rel_type=rel.rel_type.value,
        properties=rel.properties,
        valid_from=rel.valid_from.isoformat(),
        valid_to=rel.valid_to.isoformat() if rel.valid_to else None,
        version=rel.version,
        created_at=rel.created_at.isoformat(),
        updated_at=rel.updated_at.isoformat(),
    )
