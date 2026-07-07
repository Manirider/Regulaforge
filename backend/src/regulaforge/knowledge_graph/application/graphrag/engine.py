"""GraphRAGEngine — end-to-end enterprise GraphRAG pipeline orchestrator.

Coordinates retrieval (hybrid dense/sparse), reranking (cross-encoder),
context compression, grounding with source attribution and citations,
confidence scoring, evaluation, and latency benchmarking into one
production-ready pipeline.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.config.logging import get_logger

from .benchmarking import BenchmarkReport, LatencyBenchmarker
from .compressor import ContextCompressor
from .evaluation import GenerationEvaluator, RetrievalEvaluator
from .grounding import GroundingService
from .reranker import CrossEncoderReranker, RankedDocument
from .retrievers import (
    BaseRetriever,
    DenseRetriever,
    HybridRetriever,
    RetrievedDocument,
    SparseRetriever,
)

logger = get_logger(__name__)


@dataclass
class GraphRAGConfig:
    """Configuration for the GraphRAG pipeline."""

    top_k_retrieve: int = 20
    top_k_rerank: int = 10
    top_k_final: int = 10
    fusion_strategy: str = "rrf"
    rrf_k: int = 60
    compression_mode: str = "extractive"
    max_context_tokens: int = 4096
    include_citations: bool = True
    max_citations: int = 10
    citation_format: str = "markdown"
    include_confidence: bool = True
    enable_evaluation: bool = False
    enable_benchmarking: bool = False

    def __repr__(self) -> str:
        return (
            f"GraphRAGConfig(retrieve={self.top_k_retrieve}, "
            f"rerank={self.top_k_rerank}, fusion={self.fusion_strategy}, "
            f"compress={self.compression_mode})"
        )


@dataclass
class GraphRAGResponse:
    """Complete response from the GraphRAG pipeline."""

    request_id: str
    query: str
    answer: str
    retrieved_documents: list[RetrievedDocument] = field(default_factory=list)
    reranked_documents: list[RankedDocument] = field(default_factory=list)
    citations: list[Any] = field(default_factory=list)
    source_attributions: list[Any] = field(default_factory=list)
    confidence: Optional[Any] = None
    latency_ms: float = 0.0
    pipeline_steps: dict[str, float] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"GraphRAGResponse(id={self.request_id[:8]}, "
            f"query='{self.query[:40]}', retrieved={len(self.retrieved_documents)}, "
            f"latency={self.latency_ms:.1f}ms)"
        )


class GraphRAGEngine:
    """End-to-end enterprise GraphRAG pipeline.

    Usage:
        engine = GraphRAGEngine(
            dense_retriever=dense,
            sparse_retriever=sparse,
            vector_store=qdrant_store,
            kg_service=kg_service,
            llm_provider=llm,
        )
        response = await engine.query("What are the KYC norms under RBI?")
    """

    def __init__(
        self,
        dense_retriever: Optional[DenseRetriever] = None,
        sparse_retriever: Optional[SparseRetriever] = None,
        hybrid_retriever: Optional[HybridRetriever] = None,
        vector_store: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
        cross_encoder: Optional[CrossEncoderReranker] = None,
        compressor: Optional[ContextCompressor] = None,
        grounding_service: Optional[GroundingService] = None,
        kg_service: Optional[Any] = None,
        kg_query_service: Optional[Any] = None,
        llm_provider: Optional[Any] = None,
        config: Optional[GraphRAGConfig] = None,
    ) -> None:
        self._config = config or GraphRAGConfig()
        self._llm_provider = llm_provider
        self._kg_service = kg_service
        self._kg_query_service = kg_query_service

        self._vector_store = vector_store
        self._embedding_service = embedding_service

        self._dense_retriever = dense_retriever
        self._sparse_retriever = sparse_retriever
        self._hybrid_retriever = hybrid_retriever
        self._cross_encoder = cross_encoder
        self._compressor = compressor
        self._grounding = grounding_service

        self._last_retrieved_docs: list[RetrievedDocument] = []
        self._benchmarker = LatencyBenchmarker(warmup_calls=0)

        if not self._grounding:
            self._grounding = GroundingService(kg_service=kg_service)

    def _get_retriever(self) -> BaseRetriever:
        """Return the best available retriever (hybrid > dense).

        Raises RuntimeError if no retriever is configured.
        """
        if self._hybrid_retriever:
            return self._hybrid_retriever
        if self._dense_retriever:
            return self._dense_retriever
        raise RuntimeError("No retriever configured — provide dense_retriever or hybrid_retriever")

    async def retrieve(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedDocument]:
        """Stage 1: Retrieve relevant documents using hybrid search.

        Uses dense (vector) + sparse (BM25) fusion for broad coverage.
        """
        start = time.perf_counter()
        retriever = self._get_retriever()
        results = await retriever.retrieve(
            query,
            top_k=top_k or self._config.top_k_retrieve,
            filter_conditions=filter_conditions,
        )
        self._last_retrieved_docs = results
        elapsed = (time.perf_counter() - start) * 1000
        logger.info("Retrieved %d documents in %.1fms", len(results), elapsed)
        return results

    async def rerank(
        self,
        query: str,
        documents: list[RetrievedDocument],
        *,
        top_k: Optional[int] = None,
    ) -> list[RankedDocument]:
        """Stage 2: Rerank retrieved documents using cross-encoder."""
        start = time.perf_counter()

        if not self._cross_encoder:
            self._cross_encoder = CrossEncoderReranker()

        ranked = await self._cross_encoder.rerank(
            query,
            documents,
            top_k=top_k or self._config.top_k_rerank,
        )

        elapsed = (time.perf_counter() - start) * 1000
        logger.info("Reranked %d documents in %.1fms", len(ranked), elapsed)
        return ranked

    async def compress(
        self,
        query: str,
        documents: list[RankedDocument],
    ) -> Any:
        """Stage 3: Compress the retrieved context."""
        start = time.perf_counter()

        if not self._compressor:
            self._compressor = ContextCompressor(
                llm_provider=self._llm_provider,
                max_tokens=self._config.max_context_tokens,
                compression_mode=self._config.compression_mode,
            )

        compressed = await self._compressor.compress(query, documents)

        elapsed = (time.perf_counter() - start) * 1000
        logger.info("Compressed context in %.1fms (ratio=%.2f)", elapsed, compressed.compression_ratio)
        return compressed

    async def generate(
        self,
        query: str,
        context: str,
        citations: Optional[list[Any]] = None,
    ) -> str:
        """Stage 4: Generate an answer from the compressed context using LLM."""
        start = time.perf_counter()

        if not self._llm_provider:
            answer = self._default_generate(query, context, citations)
        else:
            try:
                answer = await self._llm_generate(query, context, citations)
            except Exception as e:
                logger.error("LLM generation failed: %s", str(e))
                answer = self._default_generate(query, context, citations)

        elapsed = (time.perf_counter() - start) * 1000
        logger.info("Generated answer in %.1fms", elapsed)
        return answer

    async def ground(
        self,
        query: str,
        documents: list[RankedDocument],
        answer: str,
    ) -> tuple[list[Any], list[Any], Any]:
        """Stage 5: Ground the answer with source attributions, citations, and confidence."""
        start = time.perf_counter()

        attributions = await self._grounding.build_attributions(documents) if self._grounding else []
        citations = self._grounding.build_citations(
            attributions,
            max_citations=self._config.max_citations,
            format_style=self._config.citation_format,
        ) if self._grounding else []
        confidence = self._grounding.compute_confidence(attributions, documents) if self._grounding else None

        if self._config.include_citations and citations:
            answer = self._grounding.format_answer_with_citations(answer, citations) if self._grounding else answer

        elapsed = (time.perf_counter() - start) * 1000
        logger.info("Grounded response in %.1fms", elapsed)
        return attributions, citations, confidence

    async def query(
        self,
        query_text: str,
        *,
        filter_conditions: Optional[dict[str, Any]] = None,
        config_override: Optional[GraphRAGConfig] = None,
    ) -> GraphRAGResponse:
        """End-to-end GraphRAG pipeline: retrieve -> rerank -> compress -> generate -> ground.

        Args:
            query_text: Natural language query.
            filter_conditions: Optional Qdrant payload filters.
            config_override: Per-request configuration overrides.

        Returns:
            GraphRAGResponse with answer, citations, attributions, confidence.
        """
        cfg = config_override or self._config
        request_id = str(uuid4())
        total_start = time.perf_counter()
        step_times: dict[str, float] = {}

        logger.info("GraphRAG query [%s]: '%s'", request_id[:8], query_text[:120])

        # Stage 1: Retrieve
        t0 = time.perf_counter()
        retrieved = await self.retrieve(query_text, top_k=cfg.top_k_retrieve, filter_conditions=filter_conditions)
        step_times["retrieve"] = (time.perf_counter() - t0) * 1000

        if not retrieved:
            total_elapsed = (time.perf_counter() - total_start) * 1000
            logger.info("No documents retrieved for query [%s]", request_id[:8])
            return GraphRAGResponse(
                request_id=request_id,
                query=query_text,
                answer="No relevant information found in the knowledge graph.",
                latency_ms=round(total_elapsed, 2),
                pipeline_steps=step_times,
            )

        # Stage 2: Rerank
        t0 = time.perf_counter()
        reranked = await self.rerank(query_text, retrieved, top_k=cfg.top_k_rerank)
        step_times["rerank"] = (time.perf_counter() - t0) * 1000

        # Stage 3: Compress
        t0 = time.perf_counter()
        compressed = await self.compress(query_text, reranked)
        step_times["compress"] = (time.perf_counter() - t0) * 1000

        # Stage 4: Generate
        t0 = time.perf_counter()
        answer = await self.generate(query_text, compressed.compressed_text)
        step_times["generate"] = (time.perf_counter() - t0) * 1000

        # Stage 5: Ground
        t0 = time.perf_counter()
        attributions, citations, confidence = await self.ground(query_text, reranked, answer)
        step_times["ground"] = (time.perf_counter() - t0) * 1000

        total_elapsed = (time.perf_counter() - total_start) * 1000

        return GraphRAGResponse(
            request_id=request_id,
            query=query_text,
            answer=answer,
            retrieved_documents=retrieved,
            reranked_documents=reranked,
            citations=citations,
            source_attributions=attributions,
            confidence=confidence if cfg.include_confidence else None,
            latency_ms=round(total_elapsed, 2),
            pipeline_steps=step_times,
        )

    async def evaluate(
        self,
        queries: list[str],
        relevant_docs: list[list[str]],
        *,
        generate_answers: bool = True,
    ) -> dict[str, Any]:
        """Evaluate retrieval and generation quality over a test set.

        Args:
            queries: Test query strings.
            relevant_docs: Relevant document IDs per query.
            generate_answers: Also evaluate generation quality.

        Returns:
            Dict with retrieval and optional generation evaluation results.
        """
        retrieve_tasks = [
            self.retrieve(query, top_k=self._config.top_k_retrieve)
            for query in queries
        ]
        retrieved_all: list[list[RetrievedDocument]] = list(
            await asyncio.gather(*retrieve_tasks, return_exceptions=True)
        )
        for i, r in enumerate(retrieved_all):
            if isinstance(r, Exception):
                logger.error("Retrieval failed for query '%s': %s", queries[i], r)
                retrieved_all[i] = []

        retrieval_results = RetrievalEvaluator.evaluate(queries, retrieved_all, relevant_docs)

        result: dict[str, Any] = {
            "retrieval": {
                "mean_precision": retrieval_results.mean_precision,
                "mean_recall": retrieval_results.mean_recall,
                "mean_f1": retrieval_results.mean_f1,
                "mean_mrr": retrieval_results.mean_mrr,
                "mean_ndcg": retrieval_results.mean_ndcg,
                "mean_map": retrieval_results.mean_average_precision,
                "total_queries": retrieval_results.total_queries,
                "details": [
                    {
                        "query": r.query,
                        "precision": r.precision,
                        "recall": r.recall,
                        "f1": r.f1,
                        "mrr": r.mrr,
                        "ndcg": r.ndcg,
                    }
                    for r in retrieval_results.results
                ],
            },
        }

        if generate_answers and self._llm_provider:
            evaluator = GenerationEvaluator(llm_provider=self._llm_provider)
            gen_results = []
            for query, docs in zip(queries, retrieved_all):
                response = await self.query(query)
                eval_result = await evaluator.evaluate(query, response.answer, docs)
                gen_results.append({
                    "query": query,
                    "faithfulness": eval_result.faithfulness,
                    "relevance": eval_result.relevance,
                    "completeness": eval_result.completeness,
                    "hallucination_score": eval_result.hallucination_score,
                })
            result["generation"] = gen_results

        return result

    async def benchmark(
        self,
        queries: list[str],
        *,
        concurrency: int = 5,
    ) -> BenchmarkReport:
        """Run latency and throughput benchmarking on the full pipeline.

        Args:
            queries: Benchmark query strings.
            concurrency: Parallel query count.

        Returns:
            BenchmarkReport with per-stage and overall latency stats.
        """
        retriever = self._get_retriever()

        async def _bench_retrieve(q: str) -> list[RetrievedDocument]:
            return await retriever.retrieve(q, top_k=self._config.top_k_retrieve)

        stages: list[tuple[str, Any]] = [
            ("retrieve", lambda q: _bench_retrieve(q)),
        ]

        if self._cross_encoder:
            async def _bench_rerank(q: str) -> list[RankedDocument]:
                docs = await _bench_retrieve(q)
                return await self._cross_encoder.rerank(q, docs, top_k=self._config.top_k_rerank)
            stages.append(("rerank", lambda q: _bench_rerank(q)))

        return await self._benchmarker.benchmark_pipeline(
            stages, queries=queries, concurrency=concurrency,
        )

    def _default_generate(
        self,
        query: str,
        context: str,
        citations: Optional[list[Any]] = None,
    ) -> str:
        return (
            f"Based on the retrieved information from the knowledge graph:\n\n"
            f"{context[:2000]}\n\n"
            f"This answer addresses: {query}\n\n"
            f"Note: No LLM provider configured. Install one or provide `llm_provider` "
            f"to enable AI-generated answers."
        )

    async def _llm_generate(
        self,
        query: str,
        context: str,
        citations: Optional[list[Any]] = None,
    ) -> str:
        citation_text = ""
        if citations:
            refs = "\n".join(
                f"[{c.citation_id}] {c.title} ({c.node_type})"
                for c in citations[:5]
            )
            citation_text = f"\n\nReferenced sources:\n{refs}"

        prompt = (
            "You are a regulatory compliance assistant. Answer the question based "
            "on the provided context from a knowledge graph of financial regulations "
            "(RBI, SEBI, IRDAI). Be precise, cite your sources, and note any "
            "uncertainties.\n\n"
            f"Question: {query}\n\n"
            f"Context:\n{context}\n"
            f"{citation_text}\n\n"
            "Answer:"
        )
        return await self._llm_provider.generate(prompt)

    @property
    def config(self) -> GraphRAGConfig:
        return self._config

    @config.setter
    def config(self, value: GraphRAGConfig) -> None:
        self._config = value
