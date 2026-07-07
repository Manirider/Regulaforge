"""
In-memory metrics collectors for Document Intelligence pipeline observability.

``DocIntelMetrics`` aggregates processing counters, latency histograms,
and per-stage success/failure tracking for the document processing pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProcessingMetricsCollector:
    documents_processed: int = 0
    documents_failed: int = 0
    total_pages: int = 0
    total_entities: int = 0
    total_relations: int = 0
    total_clauses: int = 0
    total_chunks: int = 0
    total_ocr_fallbacks: int = 0
    total_pipeline_time_ms: float = 0.0
    min_pipeline_time_ms: float = float("inf")
    max_pipeline_time_ms: float = 0.0
    by_stage: dict[str, int] = field(default_factory=dict)

    def record_processing(
        self,
        time_ms: float,
        pages: int = 0,
        entities: int = 0,
        relations: int = 0,
        clauses: int = 0,
        chunks: int = 0,
    ) -> None:
        self.documents_processed += 1
        self.total_pages += pages
        self.total_entities += entities
        self.total_relations += relations
        self.total_clauses += clauses
        self.total_chunks += chunks
        self.total_pipeline_time_ms += time_ms
        self.min_pipeline_time_ms = min(self.min_pipeline_time_ms, time_ms)
        self.max_pipeline_time_ms = max(self.max_pipeline_time_ms, time_ms)

    def record_failure(self) -> None:
        self.documents_failed += 1

    def record_stage(self, stage: str) -> None:
        self.by_stage[stage] = self.by_stage.get(stage, 0) + 1

    def snapshot(self) -> dict[str, int | float]:
        return {
            "documents_processed": self.documents_processed,
            "documents_failed": self.documents_failed,
            "total_pages": self.total_pages,
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "total_clauses": self.total_clauses,
            "total_chunks": self.total_chunks,
            "total_ocr_fallbacks": self.total_ocr_fallbacks,
            "total_pipeline_time_ms": self.total_pipeline_time_ms,
            "avg_pipeline_time_ms": (
                round(self.total_pipeline_time_ms / self.documents_processed, 2)
                if self.documents_processed
                else 0.0
            ),
            "min_pipeline_time_ms": (
                self.min_pipeline_time_ms if self.min_pipeline_time_ms != float("inf") else 0.0
            ),
            "max_pipeline_time_ms": self.max_pipeline_time_ms,
        }


@dataclass
class EngineMetricsCollector:
    ocr_calls: int = 0
    ocr_failures: int = 0
    ner_calls: int = 0
    ner_failures: int = 0
    layout_calls: int = 0
    layout_failures: int = 0
    clause_calls: int = 0
    clause_failures: int = 0
    chunking_calls: int = 0
    chunking_failures: int = 0
    classification_calls: int = 0
    classification_failures: int = 0
    table_extraction_calls: int = 0
    table_extraction_failures: int = 0
    chart_analysis_calls: int = 0
    chart_analysis_failures: int = 0

    def snapshot(self) -> dict[str, int]:
        return {
            "ocr_calls": self.ocr_calls,
            "ocr_failures": self.ocr_failures,
            "ner_calls": self.ner_calls,
            "ner_failures": self.ner_failures,
            "layout_calls": self.layout_calls,
            "layout_failures": self.layout_failures,
            "clause_calls": self.clause_calls,
            "clause_failures": self.clause_failures,
            "chunking_calls": self.chunking_calls,
            "chunking_failures": self.chunking_failures,
            "classification_calls": self.classification_calls,
            "classification_failures": self.classification_failures,
            "table_extraction_calls": self.table_extraction_calls,
            "table_extraction_failures": self.table_extraction_failures,
            "chart_analysis_calls": self.chart_analysis_calls,
            "chart_analysis_failures": self.chart_analysis_failures,
        }


class DocIntelMetrics:
    def __init__(self) -> None:
        self.processing = ProcessingMetricsCollector()
        self.engines = EngineMetricsCollector()

    def snapshot(self) -> dict[str, object]:
        return {
            "processing": self.processing.snapshot(),
            "engines": self.engines.snapshot(),
        }

    def reset(self) -> None:
        self.processing = ProcessingMetricsCollector()
        self.engines = EngineMetricsCollector()
