from regulaforge.graphrag.application.evaluation import EvaluationService
from regulaforge.graphrag.domain.enums import RetrievalStrategy
from regulaforge.graphrag.domain.models import (
    GroundednessReport,
    GroundednessScore,
    RankedResult,
    RetrievalResult,
    SourceAttribution,
)


def _make_result(chunk_id: str, score: float = 0.9) -> RankedResult:
    result = RetrievalResult(
        chunk_id=chunk_id,
        document_id=f"doc_{chunk_id}",
        text=f"Text for {chunk_id}",
        score=0.5,
        strategy=RetrievalStrategy.VECTOR_ONLY,
        source="test",
    )
    return RankedResult(
        result=result,
        rank=0,
        rerank_score=score,
        original_score=0.5,
    )


class TestEvaluationService:
    def test_recall_at_k_perfect(self):
        eval_svc = EvaluationService()
        retrieved = [_make_result(f"c{i}") for i in range(5)]
        relevant = {"c0", "c1", "c2"}
        recall = eval_svc.recall_at_k(retrieved, relevant, k=10)
        assert recall == 1.0

    def test_recall_at_k_partial(self):
        eval_svc = EvaluationService()
        retrieved = [_make_result(f"c{i}") for i in range(10)]
        relevant = {"c0", "c5", "c99"}
        recall = eval_svc.recall_at_k(retrieved, relevant, k=10)
        assert recall == 2.0 / 3.0

    def test_recall_at_k_empty_relevant(self):
        eval_svc = EvaluationService()
        retrieved = [_make_result("c1")]
        recall = eval_svc.recall_at_k(retrieved, set(), k=10)
        assert recall == 0.0

    def test_precision_at_k(self):
        eval_svc = EvaluationService()
        retrieved = [_make_result(f"c{i}") for i in range(10)]
        relevant = {"c0", "c2", "c4"}
        precision = eval_svc.precision_at_k(retrieved, relevant, k=5)
        assert precision == 3.0 / 5.0

    def test_precision_at_k_no_relevant(self):
        eval_svc = EvaluationService()
        retrieved = [_make_result("c1")]
        precision = eval_svc.precision_at_k(retrieved, {"c99"}, k=10)
        assert precision == 0.0

    def test_precision_at_k_empty_retrieved(self):
        eval_svc = EvaluationService()
        precision = eval_svc.precision_at_k([], {"c1"}, k=10)
        assert precision == 0.0

    def test_average_precision(self):
        eval_svc = EvaluationService()
        retrieved = [
            _make_result("c0", score=0.9),
            _make_result("c1", score=0.8),
            _make_result("c2", score=0.7),
            _make_result("c3", score=0.6),
        ]
        relevant = {"c1", "c3"}
        ap = eval_svc.average_precision(retrieved, relevant)
        assert ap > 0

    def test_mean_reciprocal_rank(self):
        eval_svc = EvaluationService()
        q1 = (
            [_make_result("c0"), _make_result("c1")],
            {"c1"},
        )
        q2 = (
            [_make_result("c99"), _make_result("c0")],
            {"c0"},
        )
        mrr = eval_svc.mean_reciprocal_rank([q1, q2])
        # q1: RR=1/2=0.5, q2: RR=1/2=0.5 -> MRR=0.5
        assert mrr == 0.5

    def test_ndcg_at_k(self):
        eval_svc = EvaluationService()
        retrieved = [
            _make_result("c0", score=0.9),
            _make_result("c1", score=0.8),
            _make_result("c2", score=0.7),
        ]
        relevant = {"c0", "c2"}
        ndcg = eval_svc.ndcg_at_k(retrieved, relevant, k=3)
        assert ndcg > 0.5

    def test_ndcg_at_k_no_relevant(self):
        eval_svc = EvaluationService()
        retrieved = [_make_result("c1")]
        ndcg = eval_svc.ndcg_at_k(retrieved, set(), k=10)
        assert ndcg == 0.0

    def test_faithfulness_score(self):
        eval_svc = EvaluationService()
        report = GroundednessReport(
            response="test",
            claims=[],
            score=GroundednessScore(faithfulness=0.85),
        )
        assert eval_svc.faithfulness_score(report) == 0.85

    def test_citation_coverage(self):
        eval_svc = EvaluationService()
        from regulaforge.graphrag.domain.models import Citation
        report = GroundednessReport(
            response="test",
            claims=[
                SourceAttribution(claim="c1", citations=[Citation(document_id="d1", document_title="D1", source="s")], is_grounded=True),
                SourceAttribution(claim="c2", citations=[], is_grounded=False),
            ],
        )
        coverage = eval_svc.citation_coverage(report)
        assert coverage == 0.5

    def test_citation_coverage_empty(self):
        eval_svc = EvaluationService()
        report = GroundednessReport(response="test", claims=[])
        assert eval_svc.citation_coverage(report) == 1.0

    def test_evaluate_retrieval(self):
        eval_svc = EvaluationService()
        data = [
            (
                "q1",
                [_make_result("c1"), _make_result("c2")],
                {"c1"},
            ),
        ]
        metrics = eval_svc.evaluate_retrieval(data, ks=[5])
        assert "recall@5" in metrics
        assert "precision@5" in metrics
        assert "map" in metrics
        assert "mrr" in metrics
        assert "ndcg@10" in metrics

    def test_evaluate_groundedness(self):
        eval_svc = EvaluationService()
        reports = [
            GroundednessReport(
                response="r1",
                claims=[SourceAttribution(claim="c1", citations=[], is_grounded=True)],
                score=GroundednessScore(overall=0.8, precision=0.8, recall=0.8, faithfulness=0.8, citation_accuracy=1.0),
            ),
        ]
        metrics = eval_svc.evaluate_groundedness(reports)
        assert metrics["avg_overall"] == 0.8
        assert metrics["avg_faithfulness"] == 0.8

    def test_full_evaluation_both(self):
        eval_svc = EvaluationService()
        data = [
            ("q1", [_make_result("c1")], {"c1"}),
        ]
        reports = [
            GroundednessReport(
                response="r1",
                claims=[],
                score=GroundednessScore(overall=0.9, precision=0.9, recall=0.9, faithfulness=0.9, citation_accuracy=1.0),
            ),
        ]
        results = eval_svc.full_evaluation(retrieval_data=data, groundedness_reports=reports)
        assert "retrieval" in results
        assert "groundedness" in results
        assert "composite_score" in results

    def test_full_evaluation_retrieval_only(self):
        eval_svc = EvaluationService()
        data = [("q1", [_make_result("c1")], {"c1"})]
        results = eval_svc.full_evaluation(retrieval_data=data)
        assert "retrieval" in results
        assert "groundedness" not in results

    def test_full_evaluation_empty(self):
        eval_svc = EvaluationService()
        results = eval_svc.full_evaluation()
        assert results == {}
