"""GraphRAG API endpoints — enterprise retrieval-augmented generation over the knowledge graph.

Exposes the full GraphRAG pipeline (retrieve -> rerank -> compress -> generate -> ground)
as RESTful endpoints with source attribution, citations, confidence scores,
evaluation, and latency benchmarking.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from regulaforge.config.constants import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from regulaforge.config.logging import get_logger
from regulaforge.knowledge_graph.application.graphrag import GraphRAGEngine
from regulaforge.knowledge_graph.application.graphrag.engine import GraphRAGConfig

logger = get_logger(__name__)

router = APIRouter(
    prefix="/knowledge-graph/graphrag",
    tags=["GraphRAG"],
)


# ---------------------------------------------------------------------------
# Singleton engine — replace with proper DI in production
# ---------------------------------------------------------------------------

_engine: Optional[GraphRAGEngine] = None
_engine_lock: asyncio.Lock = asyncio.Lock()


async def _init_engine(
    vector_host: str = "localhost",
    vector_port: int = 6333,
    collection: str = "knowledge_graph",
    cross_encoder: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
) -> GraphRAGEngine:
    """Create and return a fully configured GraphRAGEngine."""
    from regulaforge.knowledge_graph.infrastructure.qdrant_adapter import QdrantVectorStore

    vector_store = QdrantVectorStore(
        collection_name=collection,
        host=vector_host,
        port=vector_port,
    )
    await vector_store.connect()
    await vector_store.ensure_collection()

    from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService

    embedding_service = GraphEmbeddingService()

    async def _embed(text: str) -> list[float]:
        return await embedding_service.generate_query_embedding(text)

    from regulaforge.knowledge_graph.application.graphrag.retrievers import (
        DenseRetriever,
        HybridRetriever,
        SparseRetriever,
    )
    from regulaforge.knowledge_graph.application.graphrag.reranker import CrossEncoderReranker
    from regulaforge.knowledge_graph.application.graphrag.compressor import ContextCompressor
    from regulaforge.knowledge_graph.application.graphrag.grounding import GroundingService

    dense = DenseRetriever(vector_store=vector_store, embedding_fn=_embed)
    sparse = SparseRetriever()
    hybrid = HybridRetriever(dense, sparse, fusion_strategy="rrf")

    reranker = CrossEncoderReranker(model_name=cross_encoder)
    compressor = ContextCompressor(max_tokens=4096, compression_mode="extractive")
    grounding = GroundingService()

    config = GraphRAGConfig(
        top_k_retrieve=20,
        top_k_rerank=10,
        fusion_strategy="rrf",
        compression_mode="extractive",
        include_citations=True,
        include_confidence=True,
    )

    return GraphRAGEngine(
        dense_retriever=dense,
        sparse_retriever=sparse,
        hybrid_retriever=hybrid,
        cross_encoder=reranker,
        compressor=compressor,
        grounding_service=grounding,
        vector_store=vector_store,
        embedding_service=embedding_service,
        config=config,
    )


async def get_graphrag_engine() -> GraphRAGEngine:
    """Return the singleton GraphRAG engine instance (thread-safe)."""
    global _engine
    if _engine is None:
        async with _engine_lock:
            if _engine is None:
                _engine = await _init_engine()
    return _engine


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class GraphRAGQueryRequest(BaseModel):
    """Request schema for a full GraphRAG query."""

    query: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    top_k_retrieve: int = Field(default=20, ge=1, le=100, description="Documents to retrieve")
    top_k_rerank: int = Field(default=10, ge=1, le=50, description="Documents after reranking")
    fusion_strategy: str = Field(default="rrf", description="rrf or weighted")
    include_citations: bool = Field(default=True, description="Include source citations")
    compression_mode: str = Field(default="extractive", description="extractive or abstractive")
    max_context_tokens: int = Field(default=4096, ge=512, le=16384, description="Max context length")
    filter_conditions: Optional[dict[str, Any]] = Field(default=None, description="Qdrant payload filters")


class GraphRAGRetrieveRequest(BaseModel):
    """Request schema for retrieval only (no generation)."""

    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=20, ge=1, le=100)
    filter_conditions: Optional[dict[str, Any]] = Field(default=None)


class GraphRAGEvaluateRequest(BaseModel):
    """Request schema for retrieval/generation evaluation."""

    queries: list[str] = Field(..., min_length=1, description="Test queries")
    relevant_doc_ids: list[list[str]] = Field(..., description="Relevant doc IDs per query")
    evaluate_generation: bool = Field(default=True, description="Also evaluate generation")


class GraphRAGBenchmarkRequest(BaseModel):
    """Request schema for latency benchmarking."""

    queries: list[str] = Field(..., min_length=1, max_length=100, description="Benchmark queries")
    concurrency: int = Field(default=5, ge=1, le=50, description="Parallel requests")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/init")
async def initialize_engine(
    vector_host: str = Query(default="localhost", description="Qdrant host"),
    vector_port: int = Query(default=6333, description="Qdrant HTTP port"),
    collection: str = Query(default="knowledge_graph", description="Qdrant collection"),
    cross_encoder: str = Query(default="cross-encoder/ms-marco-MiniLM-L-6-v2", description="Cross-encoder model"),
) -> dict[str, Any]:
    """Initialize the GraphRAG engine with Qdrant and cross-encoder."""
    global _engine
    try:
        engine = await _init_engine(
            vector_host=vector_host,
            vector_port=vector_port,
            collection=collection,
            cross_encoder=cross_encoder,
        )
        async with _engine_lock:
            _engine = engine

        return {
            "status": "initialized",
            "vector_store": collection,
            "vector_host": vector_host,
            "vector_port": vector_port,
            "cross_encoder": cross_encoder,
            "fusion_strategy": "rrf",
        }
    except Exception as e:
        logger.error("Failed to initialize GraphRAG engine: %s", str(e))
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GraphRAG initialization failed: {e}",
        )


@router.post("/query")
async def graphrag_query(
    request: GraphRAGQueryRequest,
    engine: GraphRAGEngine = Depends(get_graphrag_engine),
) -> dict[str, Any]:
    """End-to-end GraphRAG query: retrieve -> rerank -> compress -> generate -> ground."""
    try:
        config = GraphRAGConfig(
            top_k_retrieve=request.top_k_retrieve,
            top_k_rerank=request.top_k_rerank,
            fusion_strategy=request.fusion_strategy,
            include_citations=request.include_citations,
            compression_mode=request.compression_mode,
            max_context_tokens=request.max_context_tokens,
        )
        response = await engine.query(
            request.query,
            filter_conditions=request.filter_conditions,
            config_override=config,
        )
        return {
            "request_id": response.request_id,
            "query": response.query,
            "answer": response.answer,
            "citations": [
                {
                    "id": c.citation_id,
                    "node_id": c.node_id,
                    "title": c.title,
                    "node_type": c.node_type,
                    "relevance_score": c.relevance_score,
                    "evidence_snippet": c.evidence_snippet[:200],
                }
                for c in response.citations
            ],
            "source_attributions": [
                {
                    "node_id": a.node_id,
                    "node_type": a.node_type,
                    "title": a.title,
                    "score": a.score,
                    "regulation_code": a.regulation_code,
                    "jurisdiction": a.jurisdiction,
                }
                for a in response.source_attributions
            ],
            "confidence": (
                {
                    "overall": response.confidence.overall,
                    "retrieval_quality": response.confidence.retrieval_quality,
                    "relevance": response.confidence.relevance,
                    "source_authority": response.confidence.source_authority,
                    "completeness": response.confidence.completeness,
                    "explanation": response.confidence.explanation,
                }
                if response.confidence
                else None
            ),
            "latency_ms": response.latency_ms,
            "pipeline_steps": response.pipeline_steps,
            "retrieved_count": len(response.retrieved_documents),
            "reranked_count": len(response.reranked_documents),
        }
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("GraphRAG query failed: %s", str(e))
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GraphRAG query failed: {e}",
        )


@router.post("/retrieve")
async def graphrag_retrieve(
    request: GraphRAGRetrieveRequest,
    engine: GraphRAGEngine = Depends(get_graphrag_engine),
) -> dict[str, Any]:
    """Retrieve documents without generation — for debugging and preview."""
    try:
        docs = await engine.retrieve(
            request.query,
            top_k=request.top_k,
            filter_conditions=request.filter_conditions,
        )
        return {
            "query": request.query,
            "total": len(docs),
            "results": [
                {
                    "id": d.id,
                    "title": d.title,
                    "score": d.score,
                    "source": d.source,
                    "node_type": d.node_type,
                    "node_id": d.node_id,
                    "text": d.text[:500],
                    "metadata": d.metadata,
                }
                for d in docs
            ],
        }
    except Exception as e:
        logger.error("GraphRAG retrieve failed: %s", str(e))
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {e}",
        )


@router.post("/evaluate")
async def graphrag_evaluate(
    request: GraphRAGEvaluateRequest,
    engine: GraphRAGEngine = Depends(get_graphrag_engine),
) -> dict[str, Any]:
    """Run retrieval/generation evaluation over a test set."""
    try:
        results = await engine.evaluate(
            queries=request.queries,
            relevant_docs=request.relevant_doc_ids,
            generate_answers=request.evaluate_generation,
        )
        return results
    except Exception as e:
        logger.error("GraphRAG evaluation failed: %s", str(e))
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {e}",
        )


@router.post("/benchmark")
async def graphrag_benchmark(
    request: GraphRAGBenchmarkRequest,
    engine: GraphRAGEngine = Depends(get_graphrag_engine),
) -> dict[str, Any]:
    """Run latency and throughput benchmarking on the GraphRAG pipeline."""
    try:
        report = await engine.benchmark(
            queries=request.queries,
            concurrency=request.concurrency,
        )
        return {
            "pipeline": report.pipeline,
            "total_queries": report.total_queries,
            "total_time_ms": report.total_time_ms,
            "overall_throughput_qps": report.overall_throughput_qps,
            "error_count": report.error_count,
            "stages": [
                {
                    "component": sr.component,
                    "latency": {
                        "p50_ms": sr.latency.p50_ms,
                        "p90_ms": sr.latency.p90_ms,
                        "p99_ms": sr.latency.p99_ms,
                        "mean_ms": sr.latency.mean_ms,
                        "min_ms": sr.latency.min_ms,
                        "max_ms": sr.latency.max_ms,
                        "stddev_ms": sr.latency.stddev_ms,
                    },
                    "throughput_qps": sr.throughput_qps,
                    "error_rate": sr.error_rate,
                    "total_time_ms": sr.total_time_ms,
                }
                for sr in report.stage_results
            ],
        }
    except Exception as e:
        logger.error("GraphRAG benchmark failed: %s", str(e))
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Benchmark failed: {e}",
        )


@router.get("/status")
async def graphrag_status(
    engine: GraphRAGEngine = Depends(get_graphrag_engine),
) -> dict[str, Any]:
    """Get the current GraphRAG engine status and configuration."""
    try:
        vector_store = getattr(engine, "_vector_store", None)
        info: dict[str, Any] = {}
        if vector_store:
            try:
                info = await vector_store.info()
            except Exception as e:
                info = {"error": str(e)}

        return {
            "initialized": True,
            "config": {
                "top_k_retrieve": engine.config.top_k_retrieve,
                "top_k_rerank": engine.config.top_k_rerank,
                "fusion_strategy": engine.config.fusion_strategy,
                "compression_mode": engine.config.compression_mode,
                "include_citations": engine.config.include_citations,
                "include_confidence": engine.config.include_confidence,
            },
            "vector_store": info,
            "llm_provider": getattr(engine, "_llm_provider", None) is not None,
            "cross_encoder": getattr(engine, "_cross_encoder", None) is not None,
            "sparse_retriever": getattr(engine, "_sparse_retriever", None) is not None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# Bridge — preview KG data as GraphRAG documents
# ---------------------------------------------------------------------------


@router.post("/bridge/export/{regulation_id}")
async def bridge_preview_export(
    regulation_id: str,
) -> dict[str, Any]:
    """Preview a KG regulation as GraphRAG document data (no Neo4j write)."""
    adapter: Any = None
    try:
        from regulaforge.knowledge_graph.application.knowledge_graph_graphrag_bridge import (
            KnowledgeGraphGraphRAGBridge,
        )
        from regulaforge.knowledge_graph.infrastructure.neo4j_adapter import Neo4jAdapter
        from regulaforge.knowledge_graph.application.graph_service import KnowledgeGraphService
        from regulaforge.knowledge_graph.application.graph_query_service import GraphQueryService
        from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService

        adapter = Neo4jAdapter()
        await adapter.connect()
        embedding = GraphEmbeddingService()
        kg_service = KnowledgeGraphService(
            node_repo=adapter, rel_repo=adapter, query_repo=adapter,
            embedding_service=embedding,
        )
        kg_query = GraphQueryService(
            node_repo=adapter, rel_repo=adapter, query_repo=adapter,
            embedding_service=embedding,
        )

        class _NoopGraphRAGClient:
            """No-op client that captures what would be written to GraphRAG Neo4j."""

            def __init__(self) -> None:
                self.operations: list[dict[str, Any]] = []

            async def create_document_node(self, doc: Any) -> None:
                self.operations.append({"op": "create_document", "doc_id": doc.id, "title": doc.title})

            async def create_chunk_node(self, chunk: Any) -> None:
                self.operations.append({"op": "create_chunk", "chunk_id": chunk.id})

            async def link_chunk_to_document(self, chunk_id: str, doc_id: str) -> None:
                self.operations.append({"op": "link_chunk_to_doc", "chunk_id": chunk_id, "doc_id": doc_id})

            async def create_entity_node(self, entity: dict[str, Any]) -> None:
                self.operations.append({"op": "create_entity", "entity_id": entity.get("id")})

            async def link_entity_to_chunk(self, entity_id: str, chunk_id: str, confidence: float = 0.8) -> None:
                self.operations.append({"op": "link_entity_to_chunk", "entity_id": entity_id, "chunk_id": chunk_id})

            async def query_graph(self, query: Any) -> list[Any]:
                return []

        noop = _NoopGraphRAGClient()
        bridge = KnowledgeGraphGraphRAGBridge(
            kg_service=kg_service, kg_query_service=kg_query, graphrag_neo4j=noop,
        )

        result = await bridge.export_regulation_as_document(UUID(regulation_id))
        return {
            **result,
            "graphrag_operations": noop.operations,
        }
    except ValueError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Bridge export preview failed: %s", str(e))
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export preview failed: {e}",
        )
    finally:
        if adapter is not None:
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.warning("Failed to disconnect Neo4j adapter: %s", e)
