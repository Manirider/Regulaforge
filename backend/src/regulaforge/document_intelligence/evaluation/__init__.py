"""
Evaluation metrics and benchmarks for document intelligence pipelines.

Supports precision/recall/F1 for entities, clauses, chunk boundaries,
and end-to-end pipeline benchmarking.
"""

from regulaforge.document_intelligence.evaluation.metrics import (
    Annotation,
    BenchmarkResult,
    ChunkingMetrics,
    ClauseMetrics,
    EntityMetrics,
    evaluate_chunking,
    evaluate_clauses,
    evaluate_entities,
    run_benchmark,
)

__all__ = [
    "Annotation",
    "BenchmarkResult",
    "ChunkingMetrics",
    "ClauseMetrics",
    "EntityMetrics",
    "evaluate_entities",
    "evaluate_clauses",
    "evaluate_chunking",
    "run_benchmark",
]
