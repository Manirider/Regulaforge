"""
Command-line interface for the Document Intelligence platform.

Usage:
    python -m regulaforge.document_intelligence.interfaces.cli process <file>
    python -m regulaforge.document_intelligence.interfaces.cli benchmark <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from regulaforge.document_intelligence.chunking.semantic_chunker import SentenceWindowChunker
from regulaforge.document_intelligence.extraction.clauses import RegexClauseDetector
from regulaforge.document_intelligence.extraction.metadata import PdfMetadataExtractor
from regulaforge.document_intelligence.extraction.ner import SpacyNerEngine
from regulaforge.document_intelligence.extraction.relations import RuleBasedRelationExtractor
from regulaforge.document_intelligence.layout.base import LayoutAnalyzer
from regulaforge.document_intelligence.ocr.base import OcrEngine
from regulaforge.document_intelligence.ocr.tesseract_engine import TesseractEngine
from regulaforge.document_intelligence.pipeline.orchestrator import (
    DocumentPipeline,
    OrchestratorConfig,
)


def build_pipeline(
    ocr: bool = True,
    layout: bool = False,
    ner: bool = False,
    relations: bool = False,
    clauses: bool = False,
    chunking: bool = True,
) -> DocumentPipeline:
    """Build a document pipeline with available engines."""
    ocr_engine: OcrEngine | None = None
    if ocr:
        ocr_engine = TesseractEngine()

    layout_analyzer: LayoutAnalyzer | None = None

    ner_engine = SpacyNerEngine() if ner else None
    relation_extractor = RuleBasedRelationExtractor() if relations else None
    clause_detector = RegexClauseDetector() if clauses else None
    metadata_extractor = PdfMetadataExtractor()
    chunker = SentenceWindowChunker() if chunking else None

    config = OrchestratorConfig(
        run_ocr=ocr,
        run_layout_analysis=layout,
        run_ner=ner,
        run_relation_extraction=relations,
        run_clause_detection=clauses,
        run_metadata_extraction=True,
        run_chunking=chunking,
    )

    return DocumentPipeline(
        ocr_engine=ocr_engine,
        layout_analyzer=layout_analyzer,
        ner_engine=ner_engine,
        relation_extractor=relation_extractor,
        clause_detector=clause_detector,
        metadata_extractor=metadata_extractor,
        chunker=chunker,
        config=config,
    )


async def cmd_process(args: argparse.Namespace) -> None:
    pipeline = build_pipeline(
        ocr=not args.no_ocr,
        layout=args.layout,
        ner=args.ner,
        relations=args.relations,
        clauses=args.clauses,
        chunking=not args.no_chunking,
    )

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    result = await pipeline.run(file_path)

    if args.output:
        output_path = Path(args.output)
        data = {
            "file": str(file_path),
            "stage": result.stage.value,
            "ocr": {
                "pages": len(result.ocr_result.pages) if result.ocr_result else 0,
                "confidence": round(result.ocr_result.overall_confidence, 4) if result.ocr_result else 0.0,
            } if result.ocr_result else None,
            "entities": [
                {"type": e.type.value, "text": e.text, "confidence": round(e.confidence, 4)}
                for e in (result.ner_result.entities if result.ner_result else [])
            ],
            "relations": [
                {"type": r.relation_type, "source": r.source_id, "target": r.target_id}
                for r in (result.relation_result.relations if result.relation_result else [])
            ],
            "clauses": [
                {"type": c.clause_type.value, "text": c.text[:100], "confidence": round(c.confidence, 4)}
                for c in (result.clause_result.clauses if result.clause_result else [])
            ],
            "chunks": len(result.chunking_result.chunks) if result.chunking_result else 0,
            "errors": result.errors,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Results written to {output_path}")
    else:
        print(f"Pipeline stage: {result.stage.value}")
        if result.ocr_result:
            print(f"OCR: {len(result.ocr_result.pages)} pages, "
                  f"confidence={result.ocr_result.overall_confidence:.3f}")
        if result.ner_result:
            print(f"Entities: {len(result.ner_result.entities)} found")
        if result.relation_result:
            print(f"Relations: {len(result.relation_result.relations)} found")
        if result.clause_result:
            print(f"Clauses: {len(result.clause_result.clauses)} found")
        if result.chunking_result:
            print(f"Chunks: {result.chunking_result.num_chunks}")
        if result.errors:
            print(f"Errors: {result.errors}")


async def cmd_benchmark(args: argparse.Namespace) -> None:
    from regulaforge.document_intelligence.evaluation.metrics import run_benchmark

    pipeline = build_pipeline(ocr=True, layout=False, ner=True, relations=True, clauses=True, chunking=True)
    data_dir = Path(args.data_dir)

    documents: list[tuple[Path, Path, Path | None]] = []
    for gt_file in data_dir.glob("*_gt.csv"):
        stem = gt_file.stem.replace("_gt", "")
        doc_file = data_dir / f"{stem}.pdf"
        if doc_file.exists():
            documents.append((doc_file, gt_file, None))

    print(f"Benchmarking on {len(documents)} documents...")
    bresult = await run_benchmark(pipeline, documents, num_runs=args.runs)
    print(f"Entities — Precision={bresult.entity_metrics.precision:.3f}, "
          f"Recall={bresult.entity_metrics.recall:.3f}, "
          f"F1={bresult.entity_metrics.f1:.3f}")
    print(f"Clauses  — Precision={bresult.clause_metrics.precision:.3f}, "
          f"Recall={bresult.clause_metrics.recall:.3f}, "
          f"F1={bresult.clause_metrics.f1:.3f}")
    print(f"Latency: {bresult.avg_latency_ms:.1f}ms/doc, "
          f"Throughput: {bresult.throughput_docs_per_sec:.2f} docs/sec")
    if bresult.errors:
        print(f"Errors ({len(bresult.errors)}):")
        for err in bresult.errors[:5]:
            print(f"  - {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Document Intelligence CLI")
    subparsers = parser.add_subparsers(dest="command")

    process_parser = subparsers.add_parser("process", help="Process a document")
    process_parser.add_argument("file", type=str, help="Path to document")
    process_parser.add_argument("--output", "-o", type=str, help="Output JSON path")
    process_parser.add_argument("--no-ocr", action="store_true", help="Skip OCR")
    process_parser.add_argument("--no-chunking", action="store_true", help="Skip chunking")
    process_parser.add_argument("--layout", action="store_true", help="Enable layout analysis")
    process_parser.add_argument("--ner", action="store_true", help="Enable NER")
    process_parser.add_argument("--relations", action="store_true", help="Enable relations")
    process_parser.add_argument("--clauses", action="store_true", help="Enable clause detection")

    bench_parser = subparsers.add_parser("benchmark", help="Run benchmark")
    bench_parser.add_argument("data_dir", type=str, help="Directory with PDFs and ground-truth CSVs")
    bench_parser.add_argument("--runs", type=int, default=1, help="Runs per document")

    args = parser.parse_args()
    if args.command == "process":
        import asyncio
        asyncio.run(cmd_process(args))
    elif args.command == "benchmark":
        import asyncio
        asyncio.run(cmd_benchmark(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
