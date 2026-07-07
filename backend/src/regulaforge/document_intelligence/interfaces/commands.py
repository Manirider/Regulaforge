from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from regulaforge.document_intelligence.application.chunking_service import ChunkingService
from regulaforge.document_intelligence.application.classification_service import (
    ClassificationService,
)
from regulaforge.document_intelligence.application.metadata_service import MetadataService
from regulaforge.document_intelligence.application.ner_service import NERService
from regulaforge.document_intelligence.application.ocr_service import OCRService
from regulaforge.document_intelligence.application.pipeline_service import (
    DocumentIntelligencePipeline,
)
from regulaforge.document_intelligence.application.relation_extraction import (
    RelationExtractionService,
)
from regulaforge.document_intelligence.application.table_extraction import TableExtractionService
from regulaforge.document_intelligence.infrastructure.layout.layout_analyzer import LayoutAnalyzer
from regulaforge.document_intelligence.infrastructure.pdf.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="regulaforge-docintel", description="RegulaForge Document Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    process_parser = sub.add_parser("process", help="Process a document")
    process_parser.add_argument("path", type=str, help="Path to document (PDF, image, text)")
    process_parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON path")
    process_parser.add_argument("--no-tables", action="store_true", help="Skip table extraction")
    process_parser.add_argument("--no-clauses", action="store_true", help="Skip clause extraction")
    process_parser.add_argument("--no-ner", action="store_true", help="Skip named entity recognition")
    process_parser.add_argument("--no-classification", action="store_true", help="Skip document classification")
    process_parser.add_argument("--no-chunking", action="store_true", help="Skip chunking")
    process_parser.add_argument("--no-ocr", action="store_true", help="Skip OCR fallback")

    extract_parser = sub.add_parser("extract", help="Extract specific elements")
    extract_parser.add_argument("path", type=str, help="Document path")
    extract_parser.add_argument("--element", "-e", type=str, choices=["tables", "entities", "clauses", "chunks", "metadata", "classification", "all"], default="all")  # noqa: E501

    return parser


async def run_process(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline()

    result = await pipeline.process(
        source_path=args.path,
        extract_tables=not args.no_tables,
        extract_clauses=not args.no_clauses,
        run_ner=not args.no_ner,
        run_classification=not args.no_classification,
        run_chunking=not args.no_chunking,
        ocr_fallback=not args.no_ocr,
    )

    output = result.to_dict()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    else:
        pass


async def run_extract(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline()
    result = await pipeline.process(source_path=args.path)

    if args.element == "all" or args.element == "tables":
        for _i, _t in enumerate(result.tables):
            pass

    if args.element == "all" or args.element == "entities":
        for _e in result.entities:
            pass

    if args.element == "all" or args.element == "clauses":
        for _i, _c in enumerate(result.clauses):
            pass

    if args.element == "all" or args.element == "chunks":
        for _i, _chunk in enumerate(result.chunks):
            pass

    if (args.element == "all" or args.element == "classification") and result.classification:
        pass

    if (args.element == "all" or args.element == "metadata") and result.metadata and result.metadata.summary:
        pass


def _build_pipeline() -> DocumentIntelligencePipeline:
    return DocumentIntelligencePipeline(
        pdf_processor=PDFProcessor(),
        ocr_service=OCRService(),
        layout_analyzer=LayoutAnalyzer(),
        ner_service=NERService(),
        classification_service=ClassificationService(),
        chunking_service=ChunkingService(),
        table_extraction=TableExtractionService(),
        relation_extraction=RelationExtractionService(),
        metadata_service=MetadataService(),
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if args.command == "process":
        asyncio.run(run_process(args))
    elif args.command == "extract":
        asyncio.run(run_extract(args))


if __name__ == "__main__":
    main()


def create_docintel_cli(subparsers: Any) -> None:
    """Add document intelligence subcommand to a parent argparse subparser group."""
    parser = subparsers.add_parser(
        "docintel",
        help="Document intelligence operations: process, extract",
    )
    parser.set_defaults(subsystem="docintel")
    sub = parser.add_subparsers(dest="docintel_command", required=True)

    process_parser = sub.add_parser("process", help="Process a document")
    process_parser.add_argument("path", type=str, help="Path to document (PDF, image, text)")
    process_parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON path")
    process_parser.add_argument("--no-tables", action="store_true", help="Skip table extraction")
    process_parser.add_argument("--no-clauses", action="store_true", help="Skip clause extraction")
    process_parser.add_argument("--no-ner", action="store_true", help="Skip named entity recognition")
    process_parser.add_argument("--no-classification", action="store_true", help="Skip document classification")
    process_parser.add_argument("--no-chunking", action="store_true", help="Skip chunking")
    process_parser.add_argument("--no-ocr", action="store_true", help="Skip OCR fallback")

    extract_parser = sub.add_parser("extract", help="Extract specific elements")
    extract_parser.add_argument("path", type=str, help="Document path")
    extract_parser.add_argument("--element", "-e", type=str,
                                choices=["tables", "entities", "clauses", "chunks",
                                         "metadata", "classification", "all"],
                                default="all")


DOCINTEL_COMMAND_MAP = {
    "process": run_process,
    "extract": run_extract,
}


async def handle_docintel_command(args: Any) -> None:
    cmd = getattr(args, "docintel_command", None)
    if cmd and cmd in DOCINTEL_COMMAND_MAP:
        await DOCINTEL_COMMAND_MAP[cmd](args)
    else:
        pass
