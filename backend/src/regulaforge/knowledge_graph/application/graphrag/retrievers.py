"""Hybrid retrieval — dense (vector), sparse (BM25), and fused.

Provides production-grade retrievers with async support, logging,
error handling, and configurable fusion strategies (RRF, weighted).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from regulaforge.config.logging import get_logger
from regulaforge.knowledge_graph.infrastructure.qdrant_adapter import (
    QdrantSearchResult,
    QdrantVectorStore,
)

logger = get_logger(__name__)


@dataclass
class RetrievedDocument:
    """A document retrieved from the knowledge graph with relevance info."""

    id: str
    text: str
    score: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    node_type: str = ""
    node_id: str = ""
    title: str = ""


class RetrievalError(Exception):
    """Base exception for retrieval operations."""


class BaseRetriever(ABC):
    """Abstract base for all retrievers."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 20,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedDocument]:
        ...


class DenseRetriever(BaseRetriever):
    """Dense vector retriever using Qdrant with embedding-based search."""

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        embedding_fn: Any,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_fn = embedding_fn

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 20,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedDocument]:
        logger.debug("Dense retrieve: query='%s' top_k=%d", query[:80], top_k)
        try:
            vector = await self._embedding_fn(query)
            if not vector:
                logger.warning("Empty embedding for query, returning empty results")
                return []
            results = await self._vector_store.search(
                vector=vector,
                top_k=top_k,
                filter_conditions=filter_conditions,
            )
            return [self._to_document(r) for r in results]
        except Exception as e:
            logger.error("Dense retrieval failed: %s", str(e))
            raise RetrievalError(f"Dense retrieval failed: {e}") from e

    @staticmethod
    def _to_document(result: QdrantSearchResult) -> RetrievedDocument:
        payload = result.payload or {}
        return RetrievedDocument(
            id=result.id,
            text=payload.get("text", payload.get("title", "")),
            score=result.score,
            source="dense",
            metadata=payload,
            node_type=payload.get("node_type", ""),
            node_id=payload.get("node_id", result.id),
            title=payload.get("title", ""),
        )


class SparseRetriever(BaseRetriever):
    """BM25 sparse retriever with configurable parameters.

    Builds an in-memory BM25 index from documents. For production use
    with large corpora, replace with Elasticsearch/Meilisearch backend.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ) -> None:
        self._k1 = k1
        self._b = b
        self._epsilon = epsilon
        self._documents: list[RetrievedDocument] = []
        self._bm25: Any = None
        self._initialized = False

    def index_documents(self, documents: list[RetrievedDocument]) -> None:
        """Build or rebuild the BM25 index from documents."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank_bm25 not installed, BM25 retrieval unavailable")
            self._initialized = False
            return

        if not documents:
            self._documents = []
            self._bm25 = None
            self._initialized = False
            return

        self._documents = documents
        tokenized = [self._tokenize(d.text) for d in documents]
        self._bm25 = BM25Okapi(tokenized, k1=self._k1, b=self._b, epsilon=self._epsilon)
        self._initialized = True
        logger.info("BM25 index built with %d documents", len(documents))

    def clear(self) -> None:
        """Clear the BM25 index and document store."""
        self._documents = []
        self._bm25 = None
        self._initialized = False
        logger.info("BM25 index cleared")

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 20,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedDocument]:
        if not self._initialized or self._bm25 is None:
            logger.warning("BM25 not initialized, returning empty")
            return []

        try:
            tokenized_query = self._tokenize(query)
            scores = self._bm25.get_scores(tokenized_query)
            scored = list(enumerate(scores))
            scored.sort(key=lambda x: x[1], reverse=True)

            results: list[RetrievedDocument] = []
            for idx, score in scored[:top_k]:
                doc = self._documents[idx]
                if filter_conditions:
                    if not self._match_filters(doc, filter_conditions):
                        continue
                results.append(
                    RetrievedDocument(
                        id=doc.id,
                        text=doc.text,
                        score=float(score),
                        source="sparse",
                        metadata=doc.metadata,
                        node_type=doc.node_type,
                        node_id=doc.node_id,
                        title=doc.title,
                    )
                )
            return results
        except Exception as e:
            logger.error("BM25 retrieval failed: %s", str(e))
            raise RetrievalError(f"Sparse retrieval failed: {e}") from e

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return text.lower().split()

    @staticmethod
    def _match_filters(doc: RetrievedDocument, filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            doc_value = doc.metadata.get(key)
            if isinstance(value, list):
                if doc_value not in value:
                    return False
            elif doc_value != value:
                return False
        return True


class HybridRetriever(BaseRetriever):
    """Hybrid retriever fusing dense and sparse results with RRF or weighted fusion."""

    def __init__(
        self,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        fusion_strategy: str = "rrf",
        rrf_k: int = 60,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
    ) -> None:
        self._dense = dense_retriever
        self._sparse = sparse_retriever
        self._fusion = fusion_strategy
        self._rrf_k = rrf_k
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 20,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedDocument]:
        logger.info(
            "Hybrid retrieve: query='%s' fusion=%s top_k=%d",
            query[:80], self._fusion, top_k,
        )

        dense_task = self._dense.retrieve(
            query, top_k=top_k * 2, filter_conditions=filter_conditions,
        )
        sparse_task = self._sparse.retrieve(
            query, top_k=top_k * 2, filter_conditions=filter_conditions,
        )

        import asyncio

        (dense_results, sparse_results) = await asyncio.gather(
            dense_task, sparse_task, return_exceptions=True,
        )

        if isinstance(dense_results, Exception):
            logger.warning("Dense retrieval failed: %s", dense_results)
            dense_results = []
        if isinstance(sparse_results, Exception):
            logger.warning("Sparse retrieval failed: %s", sparse_results)
            sparse_results = []

        if not dense_results and not sparse_results:
            return []

        fused = self._fuse(dense_results, sparse_results, top_k)
        logger.info(
            "Hybrid retrieve: dense=%d sparse=%d fused=%d",
            len(dense_results), len(sparse_results), len(fused),
        )
        return fused

    def _fuse(
        self,
        dense: list[RetrievedDocument],
        sparse: list[RetrievedDocument],
        top_k: int,
    ) -> list[RetrievedDocument]:
        if self._fusion == "rrf":
            return self._rrf_fusion(dense, sparse, top_k)
        elif self._fusion == "weighted":
            return self._weighted_fusion(dense, sparse, top_k)
        else:
            logger.warning("Unknown fusion '%s', falling back to RRF", self._fusion)
            return self._rrf_fusion(dense, sparse, top_k)

    def _rrf_fusion(
        self,
        dense: list[RetrievedDocument],
        sparse: list[RetrievedDocument],
        top_k: int,
    ) -> list[RetrievedDocument]:
        scores: dict[str, float] = {}
        doc_map: dict[str, RetrievedDocument] = {}

        for rank, doc in enumerate(dense):
            doc_id = doc.id
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
            doc_map[doc_id] = doc

        for rank, doc in enumerate(sparse):
            doc_id = doc.id
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for doc_id, score in ranked:
            if doc_id in doc_map:
                doc_map[doc_id].score = score

        return [doc_map[doc_id] for doc_id, _ in ranked[:top_k]]

    def _weighted_fusion(
        self,
        dense: list[RetrievedDocument],
        sparse: list[RetrievedDocument],
        top_k: int,
    ) -> list[RetrievedDocument]:
        dense_norm = self._normalize_scores(dense)
        sparse_norm = self._normalize_scores(sparse)

        combined: dict[str, tuple[float, RetrievedDocument]] = {}

        for doc in dense_norm:
            combined[doc.id] = (doc.score * self._dense_weight, doc)

        for doc in sparse_norm:
            existing_score, existing_doc = combined.get(doc.id, (0.0, doc))
            combined[doc.id] = (
                existing_score + doc.score * self._sparse_weight,
                existing_doc if doc.id in combined else doc,
            )

        ranked = sorted(combined.items(), key=lambda x: x[1][0], reverse=True)
        return [doc for _, (score, doc) in ranked[:top_k]]

    @staticmethod
    def _normalize_scores(docs: list[RetrievedDocument]) -> list[RetrievedDocument]:
        if not docs:
            return docs
        scores = [d.score for d in docs]
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return [RetrievedDocument(id=doc.id, text=doc.text, score=doc.score, source=doc.source,
                                      metadata=dict(doc.metadata), node_type=doc.node_type,
                                      node_id=doc.node_id, title=doc.title) for doc in docs]
        normalized = []
        for d in docs:
            normalized.append(
                RetrievedDocument(
                    id=d.id, text=d.text,
                    score=(d.score - min_s) / (max_s - min_s),
                    source=d.source, metadata=dict(d.metadata),
                    node_type=d.node_type, node_id=d.node_id, title=d.title,
                )
            )
        return normalized
