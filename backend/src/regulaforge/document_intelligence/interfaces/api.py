"""
FastAPI router for the Document Intelligence platform.

Endpoints:
    POST /documents/process   — process a document
    POST /documents/process-batch — process multiple documents
    GET  /documents/{id}/status   — check processing status
    GET  /health                  — health check
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile

logger = logging.getLogger(__name__)

from regulaforge.document_intelligence.chunking.semantic_chunker import SentenceWindowChunker
from regulaforge.document_intelligence.domain.enums import ProcessingStage
from regulaforge.document_intelligence.extraction.clauses import RegexClauseDetector
from regulaforge.document_intelligence.extraction.metadata import PdfMetadataExtractor
from regulaforge.document_intelligence.extraction.ner import SpacyNerEngine
from regulaforge.document_intelligence.extraction.relations import RuleBasedRelationExtractor
from regulaforge.document_intelligence.monitoring.metrics import DocIntelMetrics
from regulaforge.document_intelligence.ocr.tesseract_engine import TesseractEngine
from regulaforge.document_intelligence.pipeline.orchestrator import (
    DocumentPipeline,
    OrchestratorConfig,
    PipelineResult,
)

_metrics = DocIntelMetrics()

router = APIRouter(prefix="/documents", tags=["documents"])

_jobs: dict[str, PipelineResult] = {}


def _default_pipeline() -> DocumentPipeline:
    return DocumentPipeline(
        ocr_engine=TesseractEngine(),
        ner_engine=SpacyNerEngine(),
        relation_extractor=RuleBasedRelationExtractor(),
        clause_detector=RegexClauseDetector(),
        metadata_extractor=PdfMetadataExtractor(),
        chunker=SentenceWindowChunker(),
        config=OrchestratorConfig(
            run_ocr=True,
            run_layout_analysis=False,
            run_ner=True,
            run_relation_extraction=True,
            run_clause_detection=True,
            run_metadata_extraction=True,
            run_chunking=True,
        ),
    )


@router.post("/process")
async def process_document(
    file: UploadFile,
    run_ner: bool = True,
    run_relations: bool = True,
    run_clauses: bool = True,
    run_chunking: bool = True,
) -> dict[str, Any]:
    """Process a single uploaded document."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename or "upload")
    temp_dir = Path("__uploads__")
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / safe_name

    logger.info("Processing uploaded file: %s", safe_name)
    content = await file.read()
    temp_path.write_bytes(content)

    try:
        pipeline = _default_pipeline()
        new_config = OrchestratorConfig(
            run_ocr=True,
            run_layout_analysis=False,
            run_ner=run_ner,
            run_relation_extraction=run_relations,
            run_clause_detection=run_clauses,
            run_metadata_extraction=True,
            run_chunking=run_chunking,
        )
        pipeline.config = new_config

        result = await pipeline.run(temp_path)

        doc_id = str(hash(temp_path))
        _jobs[doc_id] = result

        _metrics.processing.record_processing(
            time_ms=0,
            pages=len(result.ocr_result.pages) if result.ocr_result else 0,
            entities=len(result.ner_result.entities) if result.ner_result else 0,
            relations=len(result.relation_result.relations) if result.relation_result else 0,
            clauses=len(result.clause_result.clauses) if result.clause_result else 0,
            chunks=len(result.chunking_result.chunks) if result.chunking_result else 0,
        )
        if result.errors:
            _metrics.processing.record_failure()

        return {
            "doc_id": doc_id,
            "stage": result.stage.value,
            "num_pages": len(result.ocr_result.pages) if result.ocr_result else 0,
            "num_entities": len(result.ner_result.entities) if result.ner_result else 0,
            "num_relations": len(result.relation_result.relations) if result.relation_result else 0,
            "num_clauses": len(result.clause_result.clauses) if result.clause_result else 0,
            "num_chunks": len(result.chunking_result.chunks) if result.chunking_result else 0,
            "errors": result.errors,
        }
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/{doc_id}/status")
async def get_status(doc_id: str) -> dict[str, Any]:
    result = _jobs.get(doc_id)
    if not result:
        raise HTTPException(404, "Document not found")
    return {
        "doc_id": doc_id,
        "stage": result.stage.value,
        "errors": result.errors,
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
async def get_metrics() -> dict[str, object]:
    return _metrics.snapshot()


def create_document_intelligence_router() -> APIRouter:
    """Create and return the Document Intelligence API router."""
    return router

