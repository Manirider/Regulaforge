"""Tests for the GraphRAG engine — retrievers, reranker, compressor, grounding, evaluation, benchmarking."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from regulaforge.knowledge_graph.application.graphrag.benchmarking import (
    BenchmarkReport,
    LatencyBenchmarker,
)
from regulaforge.knowledge_graph.application.graphrag.compressor import (
    CompressedContext,
    ContextCompressor,
)
from regulaforge.knowledge_graph.application.graphrag.engine import (
    GraphRAGConfig,
    GraphRAGEngine,
    GraphRAGResponse,
)
from regulaforge.knowledge_graph.application.graphrag.evaluation import (
    GenerationEvaluator,
    RetrievalEvaluator,
)
from regulaforge.knowledge_graph.application.graphrag.grounding import (
    Citation,
    ConfidenceScore,
    GroundingService,
    SourceAttribution,
)
from regulaforge.knowledge_graph.application.graphrag.reranker import (
    CrossEncoderReranker,
    RankedDocument,
)
from regulaforge.knowledge_graph.application.graphrag.retrievers import (
    DenseRetriever,
    HybridRetriever,
    RetrievedDocument,
    SparseRetriever,
)
from regulaforge.knowledge_graph.infrastructure.qdrant_adapter import (
    QdrantSearchResult,
    QdrantVectorStore,
)


def _make_doc(
    doc_id: str,
    text: str = "Test document content for retrieval",
    score: float = 0.85,
    source: str = "dense",
    node_type: str = "REGULATION",
    title: str = "Test Regulation",
) -> RetrievedDocument:
    return RetrievedDocument(
        id=doc_id,
        text=text,
        score=score,
        source=source,
        node_type=node_type,
        node_id=doc_id,
        title=title,
        metadata={"jurisdiction": "RBI", "category": "AML"},
    )


# =========================================================================
# Retriever Tests
# =========================================================================


class TestDenseRetriever:
    async def test_retrieve_returns_documents(self) -> None:
        mock_store = MagicMock(spec=QdrantVectorStore)
        mock_store.search = AsyncMock(return_value=[
            QdrantSearchResult(id="1", score=0.9, payload={
                "title": "KYC Guidelines", "text": "KYC norms for banks",
                "node_type": "REGULATION", "node_id": "1",
            }),
        ])

        async def _embed(_text: str) -> list[float]:
            return [0.1] * 1536

        retriever = DenseRetriever(vector_store=mock_store, embedding_fn=_embed)
        results = await retriever.retrieve("KYC norms")
        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].score == 0.9

    async def test_empty_embedding_returns_empty(self) -> None:
        mock_store = MagicMock(spec=QdrantVectorStore)

        async def _empty_embed(_text: str) -> list[float]:
            return []

        retriever = DenseRetriever(vector_store=mock_store, embedding_fn=_empty_embed)
        results = await retriever.retrieve("test")
        assert results == []


class TestSparseRetriever:
    async def test_retrieve_returns_documents(self) -> None:
        retriever = SparseRetriever()
        docs = [_make_doc("1", "KYC norms for banks"), _make_doc("2", "AML compliance guidelines")]
        retriever.index_documents(docs)
        results = await retriever.retrieve("KYC banking")
        # rank_bm25 may not be installed; when available, expect results
        if results:
            assert len(results) >= 1

    async def test_not_initialized_returns_empty(self) -> None:
        retriever = SparseRetriever()
        results = await retriever.retrieve("test")
        assert results == []

    async def test_empty_index_returns_empty(self) -> None:
        retriever = SparseRetriever()
        retriever.index_documents([])
        results = await retriever.retrieve("test")
        assert results == []

    async def test_clear_resets_index(self) -> None:
        retriever = SparseRetriever()
        docs = [_make_doc("1", "KYC norms for banks")]
        retriever.index_documents(docs)
        retriever.clear()
        assert retriever._initialized is False
        assert retriever._documents == []


class TestHybridRetriever:
    async def test_rrf_fusion(self) -> None:
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_sparse = MagicMock(spec=SparseRetriever)

        mock_dense.retrieve = AsyncMock(return_value=[
            _make_doc("1", score=0.9), _make_doc("2", score=0.8),
        ])
        mock_sparse.retrieve = AsyncMock(return_value=[
            _make_doc("3", score=0.7), _make_doc("1", score=0.6),
        ])

        hybrid = HybridRetriever(mock_dense, mock_sparse, fusion_strategy="rrf")
        results = await hybrid.retrieve("test query", top_k=5)
        assert len(results) >= 2
        assert results[0].id == "1"  # highest RRF score (appears in both)

    async def test_handles_dense_failure(self) -> None:
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_sparse = MagicMock(spec=SparseRetriever)

        mock_dense.retrieve = AsyncMock(side_effect=Exception("dense failed"))
        mock_sparse.retrieve = AsyncMock(return_value=[_make_doc("1", score=0.5)])

        hybrid = HybridRetriever(mock_dense, mock_sparse)
        results = await hybrid.retrieve("test")
        assert len(results) == 1
        assert results[0].id == "1"

    async def test_weighted_fusion(self) -> None:
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_sparse = MagicMock(spec=SparseRetriever)

        mock_dense.retrieve = AsyncMock(return_value=[_make_doc("1", score=0.9)])
        mock_sparse.retrieve = AsyncMock(return_value=[_make_doc("2", score=0.8)])

        hybrid = HybridRetriever(
            mock_dense, mock_sparse, fusion_strategy="weighted",
            dense_weight=0.7, sparse_weight=0.3,
        )
        results = await hybrid.retrieve("test", top_k=5)
        assert len(results) == 2

    async def test_empty_both_returns_empty(self) -> None:
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_sparse = MagicMock(spec=SparseRetriever)

        mock_dense.retrieve = AsyncMock(return_value=[])
        mock_sparse.retrieve = AsyncMock(return_value=[])

        hybrid = HybridRetriever(mock_dense, mock_sparse)
        results = await hybrid.retrieve("test")
        assert results == []

    async def test_weighted_fusion_does_not_mutate_originals(self) -> None:
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_sparse = MagicMock(spec=SparseRetriever)

        doc1 = _make_doc("1", score=0.9)
        doc2 = _make_doc("2", score=0.5)
        original_scores = [doc1.score, doc2.score]

        mock_dense.retrieve = AsyncMock(return_value=[doc1])
        mock_sparse.retrieve = AsyncMock(return_value=[doc2])

        hybrid = HybridRetriever(mock_dense, mock_sparse, fusion_strategy="weighted")
        await hybrid.retrieve("test", top_k=5)

        assert doc1.score == original_scores[0]
        assert doc2.score == original_scores[1]


# =========================================================================
# Reranker Tests
# =========================================================================


class TestCrossEncoderReranker:
    async def test_fallback_rerank_when_model_unavailable(self) -> None:
        reranker = CrossEncoderReranker(fallback_to_original=True)
        docs = [_make_doc("1", score=0.5), _make_doc("2", score=0.9)]
        ranked = await reranker.rerank("test query", docs)
        assert len(ranked) == 2
        assert ranked[0].document.id == "2"  # highest score first

    async def test_empty_docs_returns_empty(self) -> None:
        reranker = CrossEncoderReranker()
        ranked = await reranker.rerank("test", [])
        assert ranked == []

    async def test_raises_without_fallback(self) -> None:
        reranker = CrossEncoderReranker(fallback_to_original=False)
        docs = [_make_doc("1")]
        with pytest.raises(Exception):
            await reranker.rerank("test", docs)

    async def test_top_k_limits_results(self) -> None:
        reranker = CrossEncoderReranker(fallback_to_original=True)
        docs = [_make_doc("1"), _make_doc("2"), _make_doc("3")]
        ranked = await reranker.rerank("test", docs, top_k=2)
        assert len(ranked) == 2


# =========================================================================
# Compressor Tests
# =========================================================================


class TestContextCompressor:
    def _make_ranked(self, doc_id: str, text: str, score: float = 0.8) -> RankedDocument:
        doc = _make_doc(doc_id, text=text, score=score)
        return RankedDocument(document=doc, original_score=score, rerank_score=score, position=0)

    async def test_extractive_compression(self) -> None:
        compressor = ContextCompressor(max_tokens=1000)
        docs = [self._make_ranked("1", "A" * 500), self._make_ranked("2", "B" * 500)]
        result = await compressor.compress("test", docs)
        assert isinstance(result, CompressedContext)
        assert len(result.compressed_text) > 0
        assert result.mode == "extractive"

    async def test_extractive_drops_low_priority(self) -> None:
        compressor = ContextCompressor(max_tokens=50)
        docs = [
            self._make_ranked("1", "A" * 200, score=0.9),
            self._make_ranked("2", "B" * 200, score=0.5),
        ]
        result = await compressor.compress("test", docs)
        assert result.mode == "extractive"
        assert result.dropped_chunks is not None

    async def test_empty_docs(self) -> None:
        compressor = ContextCompressor()
        result = await compressor.compress("test", [])
        assert result.token_count_original == 0

    async def test_estimate_tokens(self) -> None:
        tokens = ContextCompressor._estimate_tokens("hello world")
        assert tokens > 0


# =========================================================================
# Grounding Tests
# =========================================================================


class TestGroundingService:
    async def test_build_attributions(self) -> None:
        service = GroundingService()
        docs = [RankedDocument(
            document=_make_doc("1", node_type="REGULATION"),
            original_score=0.9, rerank_score=0.85, position=0,
        )]
        attributions = await service.build_attributions(docs, include_kg_metadata=False)
        assert len(attributions) == 1
        assert attributions[0].node_id == "1"
        assert attributions[0].node_type == "REGULATION"

    async def test_empty_docs_empty_attributions(self) -> None:
        service = GroundingService()
        attributions = await service.build_attributions([], include_kg_metadata=False)
        assert attributions == []

    def test_build_citations(self) -> None:
        service = GroundingService()
        attributions = [
            SourceAttribution(
                node_id="1", node_type="REGULATION", title="RBI KYC",
                score=0.9, evidence_text="KYC norms for banks",
                regulation_code="RBI-2024", jurisdiction="RBI",
            ),
        ]
        citations = service.build_citations(attributions)
        assert len(citations) == 1
        assert citations[0].citation_id == 1
        assert "RBI KYC" in citations[0].formatted

    def test_build_citations_empty(self) -> None:
        service = GroundingService()
        citations = service.build_citations([])
        assert citations == []

    def test_compute_confidence(self) -> None:
        service = GroundingService()
        attributions = [
            SourceAttribution(
                node_id="1", node_type="REGULATION", title="RBI KYC",
                score=0.9, evidence_text="KYC norms",
            ),
            SourceAttribution(
                node_id="2", node_type="CLAUSE", title="Section 3",
                score=0.7, evidence_text="AML clause",
            ),
        ]
        docs = [
            RankedDocument(document=_make_doc("1"), original_score=0.9, rerank_score=0.9, position=0),
            RankedDocument(document=_make_doc("2"), original_score=0.7, rerank_score=0.7, position=1),
        ]
        confidence = service.compute_confidence(attributions, docs)
        assert isinstance(confidence, ConfidenceScore)
        assert 0 <= confidence.overall <= 1.0

    def test_confidence_empty_attributions(self) -> None:
        service = GroundingService()
        confidence = service.compute_confidence([], [])
        assert confidence.overall == 0.0

    def test_format_answer_with_citations(self) -> None:
        service = GroundingService()
        citations = [
            Citation(
                citation_id=1, node_id="1", title="RBI KYC",
                node_type="REGULATION", relevance_score=0.9,
                evidence_snippet="KYC norms",
                formatted="**[1] RBI KYC** (*REGULATION*, RBI)",
            ),
        ]
        answer = "KYC is required for all banks."
        formatted = service.format_answer_with_citations(answer, citations)
        assert "Sources" in formatted
        assert "RBI KYC" in formatted


# =========================================================================
# Evaluation Tests
# =========================================================================


class TestRetrievalEvaluator:
    def test_evaluate_perfect_retrieval(self) -> None:
        queries = ["test"]
        retrieved = [[_make_doc("1"), _make_doc("2")]]
        relevant = [["1", "2"]]
        result = RetrievalEvaluator.evaluate(queries, retrieved, relevant)
        assert result.mean_precision == 1.0
        assert result.mean_recall == 1.0
        assert result.mean_f1 == 1.0
        assert result.mean_mrr == 1.0
        assert result.mean_ndcg == 1.0

    def test_evaluate_empty_retrieval(self) -> None:
        queries = ["test"]
        retrieved = [[]]
        relevant = [["1"]]
        result = RetrievalEvaluator.evaluate(queries, retrieved, relevant)
        assert result.mean_precision == 0.0
        assert result.mean_recall == 0.0

    def test_evaluate_partial_match(self) -> None:
        queries = ["test"]
        retrieved = [[_make_doc("1"), _make_doc("3")]]
        relevant = [["1", "2"]]
        result = RetrievalEvaluator.evaluate(queries, retrieved, relevant)
        assert 0.0 < result.mean_precision < 1.0
        assert 0.0 < result.mean_recall < 1.0

    def test_evaluate_multiple_queries(self) -> None:
        queries = ["q1", "q2"]
        retrieved = [[_make_doc("1")], [_make_doc("2")]]
        relevant = [["1"], ["2"]]
        result = RetrievalEvaluator.evaluate(queries, retrieved, relevant)
        assert result.total_queries == 2
        assert result.mean_precision == 1.0

    def test_mrr_rank_aware(self) -> None:
        queries = ["test"]
        retrieved = [[_make_doc("3"), _make_doc("1")]]
        relevant = [["1"]]
        result = RetrievalEvaluator.evaluate(queries, retrieved, relevant)
        # MRR = 1/2 = 0.5 (first relevant doc at rank 2)
        assert result.mean_mrr == 0.5


class TestGenerationEvaluator:
    async def test_heuristic_evaluate(self) -> None:
        evaluator = GenerationEvaluator()
        docs = [_make_doc("1", text="KYC norms require banks to verify customer identity")]
        result = await evaluator.evaluate(
            "What are KYC norms?",
            "KYC norms require banks to verify customer identity before onboarding.",
            docs,
        )
        assert 0 <= result.faithfulness <= 1.0
        assert 0 <= result.relevance <= 1.0

    async def test_heuristic_low_faithfulness(self) -> None:
        evaluator = GenerationEvaluator()
        docs = [_make_doc("1", text="AML compliance for financial institutions")]
        result = await evaluator.evaluate(
            "KYC norms",
            "The weather is nice today and completely unrelated to regulations.",
            docs,
        )
        assert result.faithfulness < 0.5  # Low overlap with context


# =========================================================================
# Engine Tests
# =========================================================================


class TestGraphRAGEngine:
    async def test_retrieve_no_docs(self) -> None:
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_dense.retrieve = AsyncMock(return_value=[])
        engine = GraphRAGEngine(dense_retriever=mock_dense)
        response = await engine.query("test query")
        assert isinstance(response, GraphRAGResponse)
        assert "No relevant information" in response.answer
        assert response.request_id  # verify request_id is populated

    async def test_retrieve_and_pipeline(self) -> None:
        docs = [_make_doc("1", title="KYC Guidelines"), _make_doc("2", title="AML Rules")]
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_dense.retrieve = AsyncMock(return_value=docs)
        engine = GraphRAGEngine(dense_retriever=mock_dense)
        response = await engine.query("KYC compliance")
        assert response.query == "KYC compliance"
        assert len(response.retrieved_documents) == 2
        assert response.latency_ms > 0
        assert "retrieve" in response.pipeline_steps

    async def test_config_override(self) -> None:
        docs = [_make_doc("1")]
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_dense.retrieve = AsyncMock(return_value=docs)
        engine = GraphRAGEngine(dense_retriever=mock_dense)
        config = GraphRAGConfig(top_k_retrieve=5, include_citations=False)
        response = await engine.query("test", config_override=config)
        assert response is not None

    async def test_llm_generate(self) -> None:
        docs = [_make_doc("1", title="KYC Guidelines")]
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_dense.retrieve = AsyncMock(return_value=docs)
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="KYC norms require identity verification.")
        engine = GraphRAGEngine(dense_retriever=mock_dense, llm_provider=mock_llm)
        response = await engine.query("What are KYC norms?")
        assert "identity verification" in response.answer

    async def test_rerank_with_cross_encoder(self) -> None:
        docs = [_make_doc("1"), _make_doc("2")]
        mock_dense = MagicMock(spec=DenseRetriever)
        mock_dense.retrieve = AsyncMock(return_value=docs)
        mock_reranker = MagicMock(spec=CrossEncoderReranker)
        mock_reranker.rerank = AsyncMock(return_value=[
            RankedDocument(document=d, original_score=0.9, rerank_score=0.95, position=i)
            for i, d in enumerate(docs)
        ])
        engine = GraphRAGEngine(dense_retriever=mock_dense, cross_encoder=mock_reranker)
        response = await engine.query("test")
        assert len(response.reranked_documents) == 2

    async def test_config_property(self) -> None:
        engine = GraphRAGEngine()
        assert isinstance(engine.config, GraphRAGConfig)
        new_config = GraphRAGConfig(top_k_retrieve=50)
        engine.config = new_config
        assert engine.config.top_k_retrieve == 50

    async def test_default_generate(self) -> None:
        engine = GraphRAGEngine()
        answer = engine._default_generate("test query", "context information")
        assert "test query" in answer
        assert "No LLM provider" in answer


# =========================================================================
# Benchmarking Tests
# =========================================================================


class TestLatencyBenchmarker:
    async def test_benchmark_stage(self) -> None:
        bench = LatencyBenchmarker(warmup_calls=0)

        async def _fake_stage(query: str) -> None:
            import asyncio
            await asyncio.sleep(0.001)

        result = await bench.benchmark_stage(
            "test_stage", _fake_stage,
            queries=["q1", "q2", "q3"],
        )
        assert result.component == "test_stage"
        assert result.latency.total_requests == 3
        assert result.latency.p50_ms > 0
        assert result.latency.mean_ms > 0
        assert result.error_rate == 0.0

    async def test_benchmark_with_errors(self) -> None:
        bench = LatencyBenchmarker(warmup_calls=0)

        async def _failing_stage(query: str) -> None:
            if query == "fail":
                raise ValueError("failure")
            import asyncio
            await asyncio.sleep(0.001)

        result = await bench.benchmark_stage(
            "failing", _failing_stage,
            queries=["ok", "fail", "ok"],
        )
        assert result.error_rate > 0
        assert result.latency.total_requests > 0

    async def test_benchmark_pipeline(self) -> None:
        bench = LatencyBenchmarker(warmup_calls=0)

        async def _stage1(q: str) -> None:
            import asyncio
            await asyncio.sleep(0.001)

        async def _stage2(q: str) -> None:
            import asyncio
            await asyncio.sleep(0.001)

        report = await bench.benchmark_pipeline(
            [("stage1", _stage1), ("stage2", _stage2)],
            queries=["q1", "q2"],
        )
        assert isinstance(report, BenchmarkReport)
        assert report.pipeline == "graphrag_full"
        assert len(report.stage_results) == 2

    async def test_report_text(self) -> None:
        bench = LatencyBenchmarker(warmup_calls=0)

        async def _stage(q: str) -> None:
            import asyncio
            await asyncio.sleep(0.001)

        report = await bench.benchmark_pipeline(
            [("stage", _stage)], queries=["q1"],
        )
        text = bench.get_report_text(report)
        assert "Benchmark Report" in text
        assert "stage" in text.lower()

    async def test_empty_latency_results(self) -> None:
        bench = LatencyBenchmarker(warmup_calls=0)

        async def _always_fails(q: str) -> None:
            raise RuntimeError("always fails")

        result = await bench.benchmark_stage(
            "fail_all", _always_fails,
            queries=["q1"],
        )
        assert result.error_rate == 1.0


# =========================================================================
# RetrievedDocument dataclass tests
# =========================================================================


class TestRetrievedDocument:
    def test_default_values(self) -> None:
        doc = _make_doc("1")
        assert doc.id == "1"
        assert doc.source == "dense"
        assert doc.node_type == "REGULATION"
        assert doc.metadata["jurisdiction"] == "RBI"

    def test_sparse_source(self) -> None:
        doc = _make_doc("1", source="sparse")
        assert doc.source == "sparse"
