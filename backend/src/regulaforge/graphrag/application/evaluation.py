from __future__ import annotations

import logging
import math
from typing import Any, Optional

from regulaforge.graphrag.domain.models import (
    GroundednessReport,
    RankedResult,
)

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self) -> None:
        pass

    def recall_at_k(
        self,
        retrieved: list[RankedResult],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        if not relevant_ids:
            return 0.0
        top_k = retrieved[:k]
        relevant_in_top = sum(1 for r in top_k if r.result.chunk_id in relevant_ids)
        return relevant_in_top / len(relevant_ids)

    def precision_at_k(
        self,
        retrieved: list[RankedResult],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        top_k = retrieved[:k]
        if not top_k:
            return 0.0
        relevant_in_top = sum(1 for r in top_k if r.result.chunk_id in relevant_ids)
        return relevant_in_top / len(top_k)

    def average_precision(
        self,
        retrieved: list[RankedResult],
        relevant_ids: set[str],
    ) -> float:
        if not relevant_ids:
            return 0.0

        relevant_found = 0
        sum_precisions = 0.0
        for i, r in enumerate(retrieved, 1):
            if r.result.chunk_id in relevant_ids:
                relevant_found += 1
                sum_precisions += relevant_found / i

        return sum_precisions / len(relevant_ids)

    def mean_reciprocal_rank(
        self,
        queries: list[tuple[list[RankedResult], set[str]]],
    ) -> float:
        if not queries:
            return 0.0

        total_rr = 0.0
        for retrieved, relevant_ids in queries:
            for i, r in enumerate(retrieved, 1):
                if r.result.chunk_id in relevant_ids:
                    total_rr += 1.0 / i
                    break

        return total_rr / len(queries)

    def ndcg_at_k(
        self,
        retrieved: list[RankedResult],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        dcg = 0.0
        for i, r in enumerate(retrieved[:k], 1):
            rel = 1.0 if r.result.chunk_id in relevant_ids else 0.0
            dcg += (2**rel - 1) / math.log2(i + 1)

        ideal = sorted(
            [1.0 if rid in relevant_ids else 0.0 for rid in [r.result.chunk_id for r in retrieved]],
            reverse=True,
        )[:k]

        idcg = 0.0
        for i, rel in enumerate(ideal, 1):
            idcg += (2**rel - 1) / math.log2(i + 1)

        return dcg / idcg if idcg > 0 else 0.0

    def faithfulness_score(
        self,
        report: GroundednessReport,
    ) -> float:
        return report.score.faithfulness

    def citation_coverage(
        self,
        report: GroundednessReport,
    ) -> float:
        total = len(report.claims)
        if total == 0:
            return 1.0
        grounded = sum(1 for c in report.claims if c.is_grounded and c.citations)
        return grounded / total

    def evaluate_retrieval(
        self,
        query_results: list[tuple[str, list[RankedResult], set[str]]],
        ks: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        if ks is None:
            ks = [5, 10, 20]

        metrics: dict[str, Any] = {}
        for k in ks:
            recalls = []
            precisions = []
            for _query, retrieved, relevant in query_results:
                recalls.append(self.recall_at_k(retrieved, relevant, k))
                precisions.append(self.precision_at_k(retrieved, relevant, k))

            metrics[f"recall@{k}"] = sum(recalls) / len(recalls) if recalls else 0.0
            metrics[f"precision@{k}"] = sum(precisions) / len(precisions) if precisions else 0.0

        ap_scores = [
            self.average_precision(retrieved, relevant)
            for _, retrieved, relevant in query_results
        ]
        metrics["map"] = sum(ap_scores) / len(ap_scores) if ap_scores else 0.0

        mrr_input = [(retrieved, relevant) for _, retrieved, relevant in query_results]
        metrics["mrr"] = self.mean_reciprocal_rank(mrr_input)

        ndcg_scores = [
            self.ndcg_at_k(retrieved, relevant, k=10)
            for _, retrieved, relevant in query_results
        ]
        metrics["ndcg@10"] = sum(ndcg_scores) / len(ndcg_scores) if ndcg_scores else 0.0

        logger.info(
            "Retrieval evaluation: MAP=%.4f, MRR=%.4f, NDCG@10=%.4f",
            metrics["map"],
            metrics["mrr"],
            metrics["ndcg@10"],
        )
        return metrics

    def evaluate_groundedness(
        self,
        reports: list[GroundednessReport],
    ) -> dict[str, float]:
        if not reports:
            return {
                "avg_overall": 0.0,
                "avg_precision": 0.0,
                "avg_recall": 0.0,
                "avg_faithfulness": 0.0,
                "avg_citation_accuracy": 0.0,
                "avg_citation_coverage": 0.0,
            }

        n = len(reports)
        avg = {
            "avg_overall": sum(r.score.overall for r in reports) / n,
            "avg_precision": sum(r.score.precision for r in reports) / n,
            "avg_recall": sum(r.score.recall for r in reports) / n,
            "avg_faithfulness": sum(r.score.faithfulness for r in reports) / n,
            "avg_citation_accuracy": sum(r.score.citation_accuracy for r in reports) / n,
            "avg_citation_coverage": sum(
                self.citation_coverage(r) for r in reports
            ) / n,
        }
        logger.info("Groundedness evaluation: %s", avg)
        return avg

    def full_evaluation(
        self,
        retrieval_data: Optional[list[tuple[str, list[RankedResult], set[str]]]] = None,
        groundedness_reports: Optional[list[GroundednessReport]] = None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        if retrieval_data:
            results["retrieval"] = self.evaluate_retrieval(retrieval_data)
        if groundedness_reports:
            results["groundedness"] = self.evaluate_groundedness(groundedness_reports)

        if results.get("retrieval") and results.get("groundedness"):
            results["composite_score"] = (
                results["retrieval"].get("map", 0) * 0.4
                + results["groundedness"].get("avg_faithfulness", 0) * 0.4
                + results["groundedness"].get("avg_citation_accuracy", 0) * 0.2
            )

        return results
