import pytest
from regulaforge.graphrag.application.hybrid_retriever import HybridRetriever
from regulaforge.graphrag.domain.enums import RetrievalStrategy
from regulaforge.graphrag.domain.models import (
    GraphPath,
    RankedResult,
    RetrievalResult,
)


class FakeQdrant:
    async def search(self, query_vector, top_k=20, score_threshold=None, filter_conditions=None):
        return [
            {"id": "c1", "score": 0.95, "payload": {"document_id": "d1", "text": "RBI regulates banking", "source": "qdrant"}},
            {"id": "c2", "score": 0.85, "payload": {"document_id": "d2", "text": "SEBI regulates markets", "source": "qdrant"}},
        ]


class FakeBM25:
    def search(self, query, top_k=20):
        return [
            {"id": "c3", "score": 0.9, "metadata": {"document_id": "d3", "text": "IRDAI insurance regulations"}},
            {"id": "c4", "score": 0.7, "metadata": {"document_id": "d4", "text": "Compliance requirements"}},
        ]


class FakeNeo4j:
    async def query_graph(self, query):
        return [
            GraphPath(
                nodes=[{"id": "n1", "labels": ["Entity"]}, {"id": "n2", "labels": ["Chunk"]}],
                edges=[{"source": "n1", "target": "n2", "type": "HAS_ENTITY"}],
                length=1,
            )
        ]

    async def get_chunks_for_entities(self, entity_ids):
        return [
            {"chunk_id": "c5", "document_id": "d5", "text": "Graph retrieved chunk about RBI", "entities": ["RBI"]},
        ]


class FakeEmbedder:
    async def embed_query(self, query):
        return [0.1] * 384


class FakeReranker:
    async def rerank(self, query, results):
        return [
            RankedResult(result=r, rank=i + 1, rerank_score=1.0 - i * 0.1, original_score=r.score)
            for i, r in enumerate(results)
        ]


class TestHybridRetriever:
    def test_hybrid_full(self):
        import asyncio
        retriever = HybridRetriever(
            qdrant_client=FakeQdrant(),
            bm25_index=FakeBM25(),
            neo4j_client=FakeNeo4j(),
            embedding_pipeline=FakeEmbedder(),
            reranker_service=FakeReranker(),
        )
        ctx = asyncio.run(retriever.retrieve("RBI banking regulation", strategy=RetrievalStrategy.HYBRID_FULL))
        assert len(ctx.results) > 0
        assert len(ctx.citations) > 0
        assert ctx.query_time_ms >= 0
        assert len(ctx.strategies_used) >= 3

    def test_vector_only(self):
        import asyncio
        retriever = HybridRetriever(
            qdrant_client=FakeQdrant(),
            bm25_index=FakeBM25(),
            neo4j_client=FakeNeo4j(),
            embedding_pipeline=FakeEmbedder(),
            reranker_service=FakeReranker(),
        )
        ctx = asyncio.run(retriever.retrieve("RBI", strategy=RetrievalStrategy.VECTOR_ONLY))
        assert len(ctx.results) > 0
        assert RetrievalStrategy.VECTOR_ONLY in ctx.strategies_used

    def test_bm25_only(self):
        import asyncio
        retriever = HybridRetriever(
            qdrant_client=FakeQdrant(),
            bm25_index=FakeBM25(),
            neo4j_client=FakeNeo4j(),
            embedding_pipeline=FakeEmbedder(),
            reranker_service=FakeReranker(),
        )
        ctx = asyncio.run(retriever.retrieve("insurance", strategy=RetrievalStrategy.BM25_ONLY))
        assert len(ctx.results) > 0

    def test_graph_only(self):
        import asyncio
        retriever = HybridRetriever(
            qdrant_client=FakeQdrant(),
            bm25_index=FakeBM25(),
            neo4j_client=FakeNeo4j(),
            embedding_pipeline=FakeEmbedder(),
            reranker_service=FakeReranker(),
        )
        ctx = asyncio.run(retriever.retrieve("Reserve Bank of India regulation compliance", strategy=RetrievalStrategy.GRAPH_ONLY))
        assert len(ctx.results) > 0

    def test_top_k_limit(self):
        import asyncio
        retriever = HybridRetriever(
            qdrant_client=FakeQdrant(),
            bm25_index=FakeBM25(),
            neo4j_client=FakeNeo4j(),
            embedding_pipeline=FakeEmbedder(),
            reranker_service=FakeReranker(),
        )
        ctx = asyncio.run(retriever.retrieve("RBI regulation", top_k=1))
        assert len(ctx.results) <= 1

    def test_graph_paths_returned(self):
        import asyncio
        retriever = HybridRetriever(
            qdrant_client=FakeQdrant(),
            bm25_index=FakeBM25(),
            neo4j_client=FakeNeo4j(),
            embedding_pipeline=FakeEmbedder(),
            reranker_service=FakeReranker(),
        )
        ctx = asyncio.run(retriever.retrieve("Reserve Bank of India regulation compliance", strategy=RetrievalStrategy.HYBRID_FULL))
        assert len(ctx.graph_paths) > 0

    def test_citations_built(self):
        import asyncio
        retriever = HybridRetriever(
            qdrant_client=FakeQdrant(),
            bm25_index=FakeBM25(),
            neo4j_client=FakeNeo4j(),
            embedding_pipeline=FakeEmbedder(),
            reranker_service=FakeReranker(),
        )
        ctx = asyncio.run(retriever.retrieve("RBI banking", strategy=RetrievalStrategy.HYBRID_FULL))
        assert len(ctx.citations) > 0
        assert ctx.citations[0].document_id is not None
