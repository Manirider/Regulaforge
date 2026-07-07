from regulaforge.graphrag.infrastructure.cross_encoder import CrossEncoder


class TestCrossEncoder:
    def test_empty_candidates(self):
        ce = CrossEncoder()
        results = ce.rerank("test query", [])
        assert results == []

    def test_fallback_rerank_single(self):
        ce = CrossEncoder()
        candidates = [
            {"id": "c1", "text": "The Reserve Bank of India regulates banking"},
        ]
        results = ce.rerank("Reserve Bank", candidates)
        assert len(results) == 1
        assert results[0]["id"] == "c1"

    def test_fallback_rerank_ordering(self):
        ce = CrossEncoder()
        candidates = [
            {"id": "c1", "text": "weather forecast sunny skies"},
            {"id": "c2", "text": "RBI SEBI IRDAI regulatory compliance requirements"},
            {"id": "c3", "text": "banking sector regulations and compliance"},
        ]
        results = ce.rerank("regulatory compliance banking", candidates)
        assert results[0]["id"] in ("c2", "c3")
        assert results[-1]["id"] == "c1"

    def test_top_k(self):
        ce = CrossEncoder()
        candidates = [
            {"id": f"c{i}", "text": f"document number {i} about regulations"}
            for i in range(10)
        ]
        results = ce.rerank("regulations", candidates, top_k=3)
        assert len(results) == 3

    def test_scores_are_floats(self):
        ce = CrossEncoder()
        candidates = [
            {"id": "c1", "text": "test text about compliance"},
        ]
        results = ce.rerank("compliance", candidates)
        assert isinstance(results[0]["score"], float)

    def test_truncation(self):
        ce = CrossEncoder(max_length=10)
        long_text = " ".join(["word"] * 1000)
        truncated = ce._truncate(long_text)
        assert len(truncated.split()) <= 10

    def test_model_name_default(self):
        ce = CrossEncoder()
        assert ce.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
