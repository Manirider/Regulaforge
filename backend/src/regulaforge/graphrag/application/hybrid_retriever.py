from __future__ import annotations

import logging
import time
from typing import Any, Optional

from regulaforge.graphrag.domain.enums import RetrievalStrategy
from regulaforge.graphrag.domain.models import (
    Citation,
    GraphPath,
    GraphQuery,
    RankedResult,
    RetrievalResult,
    RetrievedContext,
)

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(
        self,
        qdrant_client: Any,
        bm25_index: Any,
        neo4j_client: Any,
        embedding_pipeline: Any,
        reranker_service: Any,
        vector_weight: float = 0.4,
        bm25_weight: float = 0.3,
        graph_weight: float = 0.3,
        top_k_initial: int = 50,
        top_k_final: int = 15,
    ) -> None:
        self.qdrant = qdrant_client
        self.bm25 = bm25_index
        self.neo4j = neo4j_client
        self.embedder = embedding_pipeline
        self.reranker = reranker_service
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.graph_weight = graph_weight
        self.top_k_initial = top_k_initial
        self.top_k_final = top_k_final

    async def retrieve(
        self,
        query: str,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_FULL,
        filter_conditions: Optional[dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> RetrievedContext:
        start = time.monotonic()
        top_k = top_k or self.top_k_final

        strategies_used: list[RetrievalStrategy] = []
        all_results: dict[str, RetrievalResult] = {}
        graph_paths: list[GraphPath] = []

        if strategy in (
            RetrievalStrategy.VECTOR_ONLY,
            RetrievalStrategy.HYBRID_VECTOR_BM25,
            RetrievalStrategy.HYBRID_VECTOR_GRAPH,
            RetrievalStrategy.HYBRID_FULL,
        ):
            vector_results = await self._vector_search(query, filter_conditions)
            for r in vector_results:
                if r.chunk_id not in all_results or r.score > all_results[r.chunk_id].score:
                    all_results[r.chunk_id] = r
            strategies_used.append(RetrievalStrategy.VECTOR_ONLY)

        if strategy in (
            RetrievalStrategy.BM25_ONLY,
            RetrievalStrategy.HYBRID_VECTOR_BM25,
            RetrievalStrategy.HYBRID_FULL,
        ):
            bm25_results = await self._bm25_search(query)
            for r in bm25_results:
                if r.chunk_id not in all_results or r.score > all_results[r.chunk_id].score:
                    all_results[r.chunk_id] = r
            strategies_used.append(RetrievalStrategy.BM25_ONLY)

        if strategy in (
            RetrievalStrategy.GRAPH_ONLY,
            RetrievalStrategy.HYBRID_VECTOR_GRAPH,
            RetrievalStrategy.HYBRID_FULL,
        ):
            graph_results, paths = await self._graph_search(query)
            for r in graph_results:
                if r.chunk_id not in all_results or r.score > all_results[r.chunk_id].score:
                    all_results[r.chunk_id] = r
            graph_paths.extend(paths)
            strategies_used.append(RetrievalStrategy.GRAPH_ONLY)

        results_list = list(all_results.values())
        results_list.sort(key=lambda x: x.score, reverse=True)
        results_list = results_list[:self.top_k_initial]

        reranked = await self.reranker.rerank(query, results_list)
        final_results = reranked[:top_k]

        citations = self._build_citations(final_results)

        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            "Retrieval: strategy=%s, queries=%d, results=%d, time=%.0fms",
            strategy.value,
            len(strategies_used),
            len(final_results),
            elapsed,
        )

        return RetrievedContext(
            results=final_results,
            citations=citations,
            graph_paths=graph_paths,
            query_time_ms=elapsed,
            strategies_used=strategies_used,
        )

    async def _vector_search(
        self,
        query: str,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[RetrievalResult]:
        query_vector = await self.embedder.embed_query(query)
        results = await self.qdrant.search(
            query_vector=query_vector,
            top_k=self.top_k_initial,
            filter_conditions=filter_conditions,
        )
        return [
            RetrievalResult(
                chunk_id=r["id"],
                document_id=(r.get("payload") or {}).get("document_id", ""),
                text=(r.get("payload") or {}).get("text", ""),
                score=r["score"],
                strategy=RetrievalStrategy.VECTOR_ONLY,
                source=(r.get("payload") or {}).get("source", "unknown"),
            )
            for r in results
        ]

    async def _bm25_search(self, query: str) -> list[RetrievalResult]:
        results = self.bm25.search(query, top_k=self.top_k_initial)
        return [
            RetrievalResult(
                chunk_id=r["id"],
                document_id=(r.get("metadata") or {}).get("document_id", ""),
                text=(r.get("metadata") or {}).get("text", ""),
                score=r["score"],
                strategy=RetrievalStrategy.BM25_ONLY,
                source="bm25",
            )
            for r in results
        ]

    async def _graph_search(
        self, query: str
    ) -> tuple[list[RetrievalResult], list[GraphPath]]:
        import re

        entity_names = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", query)
        entity_names = [e for e in entity_names if len(e) > 3]

        if not entity_names:
            return [], []

        graph_query = GraphQuery(
            entity_names=entity_names[:10],
            max_depth=2,
            limit=self.top_k_initial,
        )
        paths = await self.neo4j.query_graph(graph_query)

        chunk_data = await self.neo4j.get_chunks_for_entities(entity_names[:10])
        results = []
        for cd in chunk_data:
            results.append(
                RetrievalResult(
                    chunk_id=cd.get("chunk_id", ""),
                    document_id=cd.get("document_id", ""),
                    text=cd.get("text", ""),
                    score=0.8,
                    strategy=RetrievalStrategy.GRAPH_ONLY,
                    source="graph",
                    entities=[],
                )
            )

        return results, paths

    def _build_citations(
        self, results: list[RankedResult]
    ) -> list[Citation]:
        citations: list[Citation] = []
        seen_docs: set[str] = set()
        for _i, rr in enumerate(results):
            doc_id = rr.result.document_id
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                citations.append(
                    Citation(
                        document_id=doc_id,
                        document_title=rr.result.source,
                        source=rr.result.source,
                        chunk_ids=[rr.result.chunk_id],
                        relevance_scores=[rr.rerank_score],
                        page_numbers=[rr.result.page_number] if rr.result.page_number else [],
                        excerpt=rr.result.text[:300],
                    )
                )
            else:
                for c in citations:
                    if c.document_id == doc_id:
                        c.chunk_ids.append(rr.result.chunk_id)
                        c.relevance_scores.append(rr.rerank_score)
                        break
        return citations
