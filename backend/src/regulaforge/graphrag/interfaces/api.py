from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from regulaforge.graphrag.application.embedding_pipeline import EmbeddingPipeline
from regulaforge.graphrag.application.evaluation import EvaluationService
from regulaforge.graphrag.application.graph_constructor import GraphConstructor
from regulaforge.graphrag.application.graph_traversal import GraphTraversalService
from regulaforge.graphrag.application.groundedness import GroundednessChecker
from regulaforge.graphrag.application.hybrid_retriever import HybridRetriever
from regulaforge.graphrag.application.reranker_service import RerankerService
from regulaforge.graphrag.application.response_generator import ResponseGenerator
from regulaforge.graphrag.application.temporal_graph import TemporalGraphService
from regulaforge.graphrag.domain.enums import RetrievalStrategy
from regulaforge.graphrag.domain.models import TraversalConfig
from regulaforge.graphrag.infrastructure.bm25_index import BM25Index
from regulaforge.graphrag.infrastructure.cross_encoder import CrossEncoder
from regulaforge.graphrag.infrastructure.embedding_model import EmbeddingModel
from regulaforge.graphrag.infrastructure.neo4j_client import Neo4jClient
from regulaforge.graphrag.infrastructure.qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


class GraphRAGEngine:
    def __init__(self) -> None:
        self.neo4j = Neo4jClient()
        self.qdrant = QdrantClient()
        self.embedder = EmbeddingModel()
        self.bm25 = BM25Index()
        self.cross_encoder = CrossEncoder()
        self.embedding_pipeline = EmbeddingPipeline(self.embedder, self.qdrant)
        self.reranker = RerankerService(self.cross_encoder)
        self.graph_constructor = GraphConstructor(self.neo4j)
        self.graph_traversal = GraphTraversalService(self.neo4j)
        self.temporal_graph = TemporalGraphService(self.neo4j)
        self.hybrid_retriever = HybridRetriever(
            self.qdrant, self.bm25, self.neo4j,
            self.embedding_pipeline, self.reranker,
        )
        self.response_generator = ResponseGenerator()
        self.groundedness_checker = GroundednessChecker()
        self.evaluation = EvaluationService()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self.neo4j.connect()
        await self.qdrant.connect()
        await self.neo4j.create_constraints()
        self._initialized = True

    async def close(self) -> None:
        await self.neo4j.close()
        await self.qdrant.close()


_engine: Optional[GraphRAGEngine] = None


async def get_engine() -> GraphRAGEngine:
    global _engine
    if _engine is None:
        _engine = GraphRAGEngine()
        await _engine.initialize()
    return _engine


def create_graphrag_router() -> APIRouter:
    router = APIRouter(prefix="/graphrag", tags=["graphrag"])

    @router.post("/build")
    async def build_graph(
        document_id: str = Form(...),
        text: str = Form(...),
        title: str = Form(...),
        source: str = Form(...),
        doc_type: str = Form(...),
        jurisdiction: Optional[str] = Form(None),
        regulatory_body: Optional[str] = Form(None),
        published_date: Optional[str] = Form(None),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        parsed_date = None
        if published_date:
            with contextlib.suppress(ValueError):
                parsed_date = datetime.fromisoformat(published_date)
        result = await engine.graph_constructor.build_from_document(
            document_id=document_id,
            text=text,
            title=title,
            source=source,
            doc_type=doc_type,
            jurisdiction=jurisdiction,
            regulatory_body=regulatory_body,
            published_date=parsed_date,
        )
        return {"status": "success", "data": result}

    @router.post("/build/file")
    async def build_from_file(
        file: UploadFile = File(...),  # noqa: B008
        document_id: str = Form(...),
        title: str = Form(...),
        doc_type: str = Form(...),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        content = await file.read()
        text = content.decode("utf-8", errors="replace")
        result = await engine.graph_constructor.build_from_document(
            document_id=document_id,
            text=text,
            title=title,
            source=file.filename or "unknown",
            doc_type=doc_type,
        )
        return {"status": "success", "data": result}

    @router.post("/query")
    async def query(
        query_text: str = Form(...),
        strategy: str = Form("hybrid_full"),
        top_k: int = Form(15),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        strat = RetrievalStrategy(strategy)
        context = await engine.hybrid_retriever.retrieve(
            query=query_text,
            strategy=strat,
            top_k=top_k,
        )
        response = await engine.response_generator.generate(
            query=query_text,
            context=context,
        )
        groundedness = await engine.groundedness_checker.check(response, context)
        return {
            "status": "success",
            "response": response,
            "context": {
                "results_count": len(context.results),
                "citations_count": len(context.citations),
                "query_time_ms": context.query_time_ms,
                "strategies": [s.value for s in context.strategies_used],
            },
            "groundedness": {
                "overall": groundedness.score.overall,
                "precision": groundedness.score.precision,
                "recall": groundedness.score.recall,
                "faithfulness": groundedness.score.faithfulness,
                "citation_accuracy": groundedness.score.citation_accuracy,
                "ungrounded_claims": groundedness.ungrounded_claims,
            },
        }

    @router.post("/query/vector")
    async def query_vector(
        query_text: str = Form(...),
        top_k: int = Form(15),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        context = await engine.hybrid_retriever.retrieve(
            query=query_text,
            strategy=RetrievalStrategy.VECTOR_ONLY,
            top_k=top_k,
        )
        return _format_retrieval_response(context)

    @router.post("/query/bm25")
    async def query_bm25(
        query_text: str = Form(...),
        top_k: int = Form(15),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        context = await engine.hybrid_retriever.retrieve(
            query=query_text,
            strategy=RetrievalStrategy.BM25_ONLY,
            top_k=top_k,
        )
        return _format_retrieval_response(context)

    @router.post("/query/graph")
    async def query_graph(
        query_text: str = Form(...),
        top_k: int = Form(15),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        context = await engine.hybrid_retriever.retrieve(
            query=query_text,
            strategy=RetrievalStrategy.GRAPH_ONLY,
            top_k=top_k,
        )
        return _format_retrieval_response(context)

    @router.post("/traverse")
    async def traverse(
        entity_name: str = Form(...),
        max_depth: int = Form(3),
        max_branches: int = Form(10),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        config = TraversalConfig(
            max_depth=max_depth,
            max_branches=max_branches,
        )
        paths = await engine.graph_traversal.traverse_from_entity(
            entity_name=entity_name,
            config=config,
        )
        return {
            "status": "success",
            "entity": entity_name,
            "paths": [
                {
                    "length": p.length,
                    "score": p.score,
                    "nodes": [
                        {"id": n["id"], "labels": n["labels"]}
                        for n in p.nodes
                    ],
                    "edges": [
                        {"source": e["source"], "target": e["target"], "type": e["type"]}
                        for e in p.edges
                    ],
                }
                for p in paths
            ],
        }

    @router.post("/traverse/between")
    async def traverse_between(
        source_entity: str = Form(...),
        target_entity: str = Form(...),
        max_depth: int = Form(4),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        path = await engine.graph_traversal.traverse_between(
            source_entity=source_entity,
            target_entity=target_entity,
            max_depth=max_depth,
        )
        if path is None:
            return {"status": "success", "path": None, "found": False}
        return {
            "status": "success",
            "found": True,
            "path": {
                "length": path.length,
                "nodes": [{"id": n["id"], "labels": n["labels"]} for n in path.nodes],
                "edges": [
                    {"source": e["source"], "target": e["target"], "type": e["type"]}
                    for e in path.edges
                ],
            },
        }

    @router.post("/temporal/query")
    async def temporal_query(
        entity_name: str = Form(...),
        start_date: Optional[str] = Form(None),
        end_date: Optional[str] = Form(None),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        parsed_start = datetime.fromisoformat(start_date) if start_date else None
        parsed_end = datetime.fromisoformat(end_date) if end_date else None
        timeline = await engine.temporal_graph.get_timeline(
            entity_name=entity_name,
            start_date=parsed_start,
            end_date=parsed_end,
        )
        return {"status": "success", "entity": entity_name, "events": timeline}

    @router.post("/temporal/timeline")
    async def temporal_timeline(
        entity_name: str = Form(...),
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        events = await engine.temporal_graph.get_timeline(entity_name=entity_name)
        return {"status": "success", "entity": entity_name, "events": events}

    @router.get("/status")
    async def status(
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        neo4j_status = "connected" if engine.neo4j._driver else "disconnected"
        qdrant_info = {"status": "unknown"}
        try:
            qdrant_info = await engine.qdrant.collection_info()
        except Exception as exc:
            qdrant_info = {"status": f"error: {exc}"}

        return {
            "status": "running",
            "neo4j": neo4j_status,
            "qdrant": qdrant_info,
            "embedding_model": engine.embedder.model_name,
            "cross_encoder": engine.cross_encoder.model_name,
        }

    @router.delete("/graph")
    async def clear_graph(
        engine: GraphRAGEngine = Depends(get_engine),  # noqa: B008
    ) -> dict[str, Any]:
        await engine.neo4j.delete_all()
        return {"status": "success", "message": "Graph cleared"}

    return router


def _format_retrieval_response(context: Any) -> dict[str, Any]:
    return {
        "status": "success",
        "results": [
            {
                "chunk_id": r.result.chunk_id,
                "document_id": r.result.document_id,
                "score": r.rerank_score,
                "strategy": r.result.strategy.value,
                "text_preview": r.result.text[:300],
                "entities": [e.name for e in r.result.entities],
            }
            for r in context.results
        ],
        "citations": [
            {
                "document_id": c.document_id,
                "document_title": c.document_title,
                "relevance_score": c.relevance_scores[0] if c.relevance_scores else 0,
                "excerpt": c.excerpt,
            }
            for c in context.citations
        ],
        "query_time_ms": context.query_time_ms,
        "strategies_used": [s.value for s in context.strategies_used],
    }
