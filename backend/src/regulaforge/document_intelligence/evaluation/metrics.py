"""
Evaluation metrics for document intelligence pipeline stages.

Ground-truth annotations are compared against pipeline predictions
to compute precision, recall, and F1 scores for entities, clauses,
and chunk boundaries.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from regulaforge.document_intelligence.domain.models import (
    ExtractedEntity,
    IdentifiedClause,
    SemanticChunk,
)
from regulaforge.document_intelligence.pipeline.orchestrator import DocumentPipeline, PipelineResult


@dataclass
class EntityMetrics:
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0


@dataclass
class ClauseMetrics:
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0


@dataclass
class ChunkingMetrics:
    boundary_precision: float = 0.0
    boundary_recall: float = 0.0
    boundary_f1: float = 0.0


@dataclass
class Annotation:
    text: str
    type: str
    start: int | None = None
    end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    entity_metrics: EntityMetrics = field(default_factory=EntityMetrics)
    clause_metrics: ClauseMetrics = field(default_factory=ClauseMetrics)
    chunking_metrics: ChunkingMetrics = field(default_factory=ChunkingMetrics)
    avg_latency_ms: float = 0.0
    throughput_docs_per_sec: float = 0.0
    num_docs: int = 0
    errors: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return text.strip().lower()


def evaluate_entities(
    predictions: list[ExtractedEntity],
    ground_truth: list[Annotation],
    type_filter: str | None = None,
) -> EntityMetrics:
    """Compute precision, recall, F1 for entity extraction.

    An entity is considered a true positive if its text (normalised)
    matches a ground-truth annotation of the same type.
    """
    pred_set = {
        (_normalize(e.text), e.type.value)
        for e in predictions
        if type_filter is None or e.type.value == type_filter
    }
    gt_set = {
        (_normalize(a.text), a.type)
        for a in ground_truth
        if type_filter is None or a.type == type_filter
    }

    true_positives = len(pred_set & gt_set)
    false_positives = len(pred_set - gt_set)
    false_negatives = len(gt_set - pred_set)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return EntityMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def evaluate_clauses(
    predictions: list[IdentifiedClause],
    ground_truth: list[Annotation],
) -> ClauseMetrics:
    """Compute precision, recall, F1 for clause detection.

    Uses normalised text overlap for matching.
    """
    pred_set = {
        (_normalize(c.text), c.clause_type.value)
        for c in predictions
    }
    gt_set = {
        (_normalize(a.text), a.type)
        for a in ground_truth
    }

    true_positives = len(pred_set & gt_set)
    false_positives = len(pred_set - gt_set)
    false_negatives = len(gt_set - pred_set)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return ClauseMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def evaluate_chunking(
    predictions: list[SemanticChunk],
    ground_truth: list[dict[str, Any]],
) -> ChunkingMetrics:
    """Evaluate chunk boundary detection.

    Ground-truth boundaries are given as character offsets (``"start"``,
    ``"end"``).  Each predicted chunk's character span is compared against
    the ground-truth spans; a true positive is recorded when the predicted
    chunk's span overlaps a ground-truth span with an IoU > 0.5.
    """
    pred_spans: list[tuple[int, int]] = []
    for chunk in predictions:
        meta = chunk.metadata or {}
        cs = meta.get("char_start")
        ce = meta.get("char_end")
        if cs is not None and ce is not None:
            pred_spans.append((int(cs), int(ce)))

    gt_spans: list[tuple[int, int]] = []
    for gt in ground_truth:
        start = gt.get("start", 0) if isinstance(gt, dict) else 0
        end = gt.get("end", 0) if isinstance(gt, dict) else 0
        gt_spans.append((int(start), int(end)))

    if not pred_spans or not gt_spans:
        return ChunkingMetrics()

    true_positives = 0
    matched_gt: set[int] = set()
    for pi, (ps, pe) in enumerate(pred_spans):
        for gi, (gs, ge) in enumerate(gt_spans):
            if gi in matched_gt:
                continue
            intersection = max(0, min(pe, ge) - max(ps, gs))
            union = max(pe, ge) - min(ps, gs)
            if union > 0 and intersection / union > 0.5:
                true_positives += 1
                matched_gt.add(gi)
                break

    false_positives = len(pred_spans) - true_positives
    false_negatives = len(gt_spans) - true_positives

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return ChunkingMetrics(
        boundary_precision=precision,
        boundary_recall=recall,
        boundary_f1=f1,
    )


def load_ground_truth(path: Path) -> list[Annotation]:
    """Load annotations from a CSV file.

    CSV columns: text, type, start, end, metadata (JSON).
    """
    annotations: list[Annotation] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            annotations.append(
                Annotation(
                    text=row.get("text", ""),
                    type=row.get("type", ""),
                    start=int(row["start"]) if row.get("start") else None,
                    end=int(row["end"]) if row.get("end") else None,
                )
            )
    return annotations


async def run_benchmark(
    pipeline: DocumentPipeline,
    documents: list[tuple[Path, Path, Path | None]],
    num_runs: int = 1,
) -> BenchmarkResult:
    """Run a benchmark over a set of documents with ground-truth annotations.

    Args:
        pipeline: Configured ``DocumentPipeline`` instance.
        documents: List of ``(file_path, ground_truth_csv, image_dir_or_none)``
            tuples.
        num_runs: Number of times to process each document (for latency).

    Returns:
        Aggregated ``BenchmarkResult``.
    """
    all_entity_preds: list[list[ExtractedEntity]] = []
    all_entity_gts: list[list[Annotation]] = []
    all_clause_preds: list[list[IdentifiedClause]] = []
    all_clause_gts: list[list[Annotation]] = []
    latencies_ms: list[float] = []
    errors: list[str] = []

    for file_path, gt_csv, image_dir in documents:
        gt_annotations = load_ground_truth(gt_csv)

        for _ in range(num_runs):
            start = time.perf_counter()
            try:
                image_paths: list[Path] = []
                if image_dir and image_dir.is_dir():
                    image_paths = sorted(image_dir.glob("*.png")) + sorted(image_dir.glob("*.jpg"))

                result: PipelineResult = await pipeline.run(
                    file_path=file_path,
                    image_paths=image_paths or None,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies_ms.append(elapsed_ms)

                if result.ner_result:
                    all_entity_preds.append(result.ner_result.entities)
                    entity_types = {e.type.value for e in result.ner_result.entities}
                    all_entity_gts.append([
                        a for a in gt_annotations
                        if a.type in entity_types
                    ])

                if result.clause_result:
                    all_clause_preds.append(result.clause_result.clauses)
                    clause_types = {c.clause_type.value for c in result.clause_result.clauses}
                    all_clause_gts.append([
                        a for a in gt_annotations
                        if a.type in clause_types
                    ])

                if result.errors:
                    errors.extend(result.errors.values())
            except Exception as exc:
                errors.append(f"{file_path.name}: {exc}")

    entity_preds_flat = [e for sublist in all_entity_preds for e in sublist]
    entity_gts_flat = [e for sublist in all_entity_gts for e in sublist]
    clause_preds_flat = [c for sublist in all_clause_preds for c in sublist]
    clause_gts_flat = [c for sublist in all_clause_gts for c in sublist]

    entity_metrics = evaluate_entities(entity_preds_flat, entity_gts_flat)
    clause_metrics = evaluate_clauses(clause_preds_flat, clause_gts_flat)

    total_docs = len(documents) * num_runs
    total_time_s = sum(latencies_ms) / 1000 if latencies_ms else 0.001
    throughput = total_docs / total_time_s if total_time_s > 0 else 0.0
    avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0

    return BenchmarkResult(
        entity_metrics=entity_metrics,
        clause_metrics=clause_metrics,
        avg_latency_ms=avg_latency,
        throughput_docs_per_sec=throughput,
        num_docs=total_docs,
        errors=errors,
    )
