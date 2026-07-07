"""Evaluation metrics for GraphRAG retrieval and generation quality.

Provides precision, recall, MRR, NDCG, MAP for retrieval evaluation,
plus faithfulness, relevance, and completeness for generation evaluation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from regulaforge.config.logging import get_logger

from .retrievers import RetrievedDocument

logger = get_logger(__name__)


@dataclass
class RetrievalEvalResult:
    """Evaluation results for a single retrieval query."""

    query: str
    precision: float
    recall: float
    f1: float
    mrr: float
    ndcg: float
    average_precision: float
    retrieved_count: int
    relevant_count: int


@dataclass
class RetrievalEvalSummary:
    """Aggregated retrieval evaluation results."""

    total_queries: int
    mean_precision: float
    mean_recall: float
    mean_f1: float
    mean_mrr: float
    mean_ndcg: float
    mean_average_precision: float
    results: list[RetrievalEvalResult] = field(default_factory=list)


@dataclass
class GenerationEvalResult:
    """Evaluation results for a generated response."""

    query: str
    faithfulness: float
    relevance: float
    completeness: float
    hallucination_score: float


class RetrievalEvaluator:
    """Evaluates retrieval quality using standard IR metrics."""

    @staticmethod
    def evaluate(
        queries: list[str],
        retrieved: list[list[RetrievedDocument]],
        relevant: list[list[str]],
    ) -> RetrievalEvalSummary:
        """Evaluate retrieval quality across multiple queries.

        Args:
            queries: List of query strings.
            retrieved: List of retrieved document lists per query.
            relevant: List of relevant document ID lists per query.

        Returns:
            Aggregated evaluation summary.
        """
        results: list[RetrievalEvalResult] = []
        for q, retrieved_docs, relevant_ids in zip(queries, retrieved, relevant):
            retrieved_ids = [d.id for d in retrieved_docs]
            result = RetrievalEvaluator._evaluate_single(q, retrieved_ids, relevant_ids)
            results.append(result)

        n = len(results)
        return RetrievalEvalSummary(
            total_queries=n,
            mean_precision=sum(r.precision for r in results) / n if n else 0.0,
            mean_recall=sum(r.recall for r in results) / n if n else 0.0,
            mean_f1=sum(r.f1 for r in results) / n if n else 0.0,
            mean_mrr=sum(r.mrr for r in results) / n if n else 0.0,
            mean_ndcg=sum(r.ndcg for r in results) / n if n else 0.0,
            mean_average_precision=sum(r.average_precision for r in results) / n if n else 0.0,
            results=results,
        )

    @staticmethod
    def _evaluate_single(
        query: str,
        retrieved: list[str],
        relevant: list[str],
    ) -> RetrievalEvalResult:
        relevant_set = set(relevant)
        retrieved_set = set(retrieved)

        true_positives = len(retrieved_set & relevant_set)
        precision = true_positives / len(retrieved) if retrieved else 0.0
        recall = true_positives / len(relevant) if relevant else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # MRR
        mrr = 0.0
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant_set:
                mrr = 1.0 / (i + 1)
                break

        # NDCG
        dcg = 0.0
        idcg = 0.0
        for i, doc_id in enumerate(retrieved):
            rel = 1.0 if doc_id in relevant_set else 0.0
            dcg += (2**rel - 1) / math.log2(i + 2)
        for i in range(min(len(relevant), len(retrieved))):
            idcg += (2**1 - 1) / math.log2(i + 2)
        ndcg = dcg / idcg if idcg > 0 else 0.0

        # MAP
        avg_precision = 0.0
        correct_so_far = 0
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant_set:
                correct_so_far += 1
                avg_precision += correct_so_far / (i + 1)
        avg_precision = avg_precision / len(relevant) if relevant else 0.0

        return RetrievalEvalResult(
            query=query,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            mrr=round(mrr, 4),
            ndcg=round(ndcg, 4),
            average_precision=round(avg_precision, 4),
            retrieved_count=len(retrieved),
            relevant_count=len(relevant),
        )


class GenerationEvaluator:
    """Evaluates generation quality using LLM-based or heuristic metrics."""

    def __init__(self, llm_provider: Optional[Any] = None) -> None:
        self._llm_provider = llm_provider

    async def evaluate(
        self,
        query: str,
        generated_answer: str,
        retrieved_docs: list[RetrievedDocument],
    ) -> GenerationEvalResult:
        """Evaluate a generated response for faithfulness, relevance, and completeness.

        Uses LLM-based evaluation when available, falls back to heuristic metrics.
        """
        if self._llm_provider:
            return await self._llm_evaluate(query, generated_answer, retrieved_docs)
        return self._heuristic_evaluate(query, generated_answer, retrieved_docs)

    async def _llm_evaluate(
        self,
        query: str,
        generated_answer: str,
        retrieved_docs: list[RetrievedDocument],
    ) -> GenerationEvalResult:
        try:
            context = "\n".join(f"[{i + 1}] {d.text[:500]}" for i, d in enumerate(retrieved_docs[:5]))
            prompt = (
                "Evaluate the following answer for a query based on the provided context.\n\n"
                f"Query: {query}\n\n"
                f"Context:\n{context}\n\n"
                f"Answer:\n{generated_answer}\n\n"
                "Rate each metric 0.0-1.0:\n"
                "- faithfulness: Is the answer supported by the context?\n"
                "- relevance: How well does the answer address the query?\n"
                "- completeness: Does the answer cover all aspects of the query?\n"
                "- hallucination_score: How much unsupported content? (1.0 = no hallucination)\n\n"
                "Return as JSON: {\"faithfulness\": 0.0, \"relevance\": 0.0, \"completeness\": 0.0, \"hallucination_score\": 0.0}"
            )
            response = await self._llm_provider.generate(prompt)
            import json

            parsed = json.loads(response)
            return GenerationEvalResult(
                query=query,
                faithfulness=float(parsed.get("faithfulness", 0.5)),
                relevance=float(parsed.get("relevance", 0.5)),
                completeness=float(parsed.get("completeness", 0.5)),
                hallucination_score=float(parsed.get("hallucination_score", 0.5)),
            )
        except Exception as e:
            logger.error("LLM evaluation failed: %s", str(e))
            return self._heuristic_evaluate(query, generated_answer, retrieved_docs)

    @staticmethod
    def _heuristic_evaluate(
        query: str,
        generated_answer: str,
        retrieved_docs: list[RetrievedDocument],
    ) -> GenerationEvalResult:
        context_text = " ".join(d.text.lower() for d in retrieved_docs)
        answer_lower = generated_answer.lower()
        answer_words = set(answer_lower.split())

        context_words = set(context_text.split())
        overlap = answer_words & context_words
        faithfulness = len(overlap) / max(len(answer_words), 1) if answer_words else 0.0
        faithfulness = min(1.0, faithfulness * 1.2)

        query_words = set(query.lower().split())
        query_overlap = answer_words & query_words
        relevance = len(query_overlap) / max(len(query_words), 1) if query_words else 0.5
        relevance = min(1.0, relevance * 1.5)

        answer_length_ratio = len(generated_answer.split()) / max(
            sum(len(d.text.split()) for d in retrieved_docs[:3]), 1,
        )
        completeness = min(1.0, answer_length_ratio * 3)

        return GenerationEvalResult(
            query=query,
            faithfulness=round(faithfulness, 3),
            relevance=round(relevance, 3),
            completeness=round(completeness, 3),
            hallucination_score=round(faithfulness, 3),
        )
