import pytest
from regulaforge.graphrag.application.reranker_service import RerankerService
from regulaforge.graphrag.domain.enums import RetrievalStrategy
from regulaforge.graphrag.domain.models import RetrievalResult


class FakeCrossEncoder:
    def rerank(self, query: str, candidates: list[dict], top_k=None):
        scored = []
        for i, c in enumerate(candidates):
            text_lower = c["text"].lower()
            query_lower = query.lower()
            query_terms = set(query_lower.split())
            text_terms = set(text_lower.split())
            overlap = len(query_terms & text_terms)
            score = overlap / len(query_terms) if query_terms else 0
            scored.append({"id": c["id"], "score": score, "original_rank": i})
        scored.sort(key=lambda x: x["score"], reverse=True)
        if top_k:
            scored = scored[:top_k]
        return scored


class TestRerankerService:
    def test_empty_results(self):
        import asyncio
        ce = FakeCrossEncoder()
        reranker = RerankerService(ce)
        results = asyncio.run(reranker.rerank("query", []))
        assert results == []

    def test_rerank_orders_by_score(self):
        ce = FakeCrossEncoder()
        reranker = RerankerService(ce)
        results = [
            RetrievalResult(chunk_id="c1", document_id="d1", text="weather report",
                            score=0.9, strategy=RetrievalStrategy.VECTOR_ONLY, source="t"),
            RetrievalResult(chunk_id="c2", document_id="d2", text="RBI regulation compliance",
                            score=0.8, strategy=RetrievalStrategy.BM25_ONLY, source="t"),
            RetrievalResult(chunk_id="c3", document_id="d3", text="banking regulation RBI compliance",
                            score=0.7, strategy=RetrievalStrategy.GRAPH_ONLY, source="t"),
        ]
        import asyncio
        reranked = asyncio.run(reranker.rerank("RBI regulation compliance", results))

        assert len(reranked) == 3
        assert reranked[0].result.chunk_id in ("c2", "c3")

    def test_rerank_assigns_ranks(self):
        ce = FakeCrossEncoder()
        reranker = RerankerService(ce)
        results = [
            RetrievalResult(chunk_id="c1", document_id="d1", text="RBI compliance",
                            score=0.5, strategy=RetrievalStrategy.VECTOR_ONLY, source="t"),
            RetrievalResult(chunk_id="c2", document_id="d2", text="weather",
                            score=0.5, strategy=RetrievalStrategy.VECTOR_ONLY, source="t"),
        ]
        import asyncio
        reranked = asyncio.run(reranker.rerank("RBI compliance", results))
        for r in reranked:
            assert r.rank >= 1
        assert reranked[0].rank == 1

    def test_min_score_filter(self):
        ce = FakeCrossEncoder()
        reranker = RerankerService(ce, min_score=0.5)
        results = [
            RetrievalResult(chunk_id="c1", document_id="d1", text="RBI compliance regulation",
                            score=0.5, strategy=RetrievalStrategy.VECTOR_ONLY, source="t"),
            RetrievalResult(chunk_id="c2", document_id="d2", text="weather sunny clear",
                            score=0.5, strategy=RetrievalStrategy.VECTOR_ONLY, source="t"),
        ]
        import asyncio
        reranked = asyncio.run(reranker.rerank("RBI compliance regulation", results))
        assert len(reranked) == 1

    def test_top_k(self):
        ce = FakeCrossEncoder()
        reranker = RerankerService(ce, top_k=1)
        results = [
            RetrievalResult(chunk_id=f"c{i}", document_id=f"d{i}", text="RBI compliance",
                            score=0.5, strategy=RetrievalStrategy.VECTOR_ONLY, source="t")
            for i in range(5)
        ]
        import asyncio
        reranked = asyncio.run(reranker.rerank("RBI compliance", results))
        assert len(reranked) <= 1
