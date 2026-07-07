"""
Integration hook between ingestion ETL and Document Intelligence pipeline.

After the ingestion subsystem extracts text from a regulatory document,
this hook triggers the Document Intelligence pipeline for deeper analysis:
NER, relation extraction, clause detection, chunking, and metadata extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path

from regulaforge.document_intelligence.chunking.semantic_chunker import SentenceWindowChunker
from regulaforge.document_intelligence.extraction.clauses import RegexClauseDetector
from regulaforge.document_intelligence.extraction.metadata import PdfMetadataExtractor, TextMetadataExtractor
from regulaforge.document_intelligence.extraction.ner import SpacyNerEngine
from regulaforge.document_intelligence.extraction.relations import RuleBasedRelationExtractor
from regulaforge.document_intelligence.ocr.tesseract_engine import TesseractEngine
from regulaforge.document_intelligence.pipeline.orchestrator import (
    DocumentPipeline,
    OrchestratorConfig,
)

logger = logging.getLogger(__name__)

_default_pipeline: DocumentPipeline | None = None


def _get_pipeline() -> DocumentPipeline:
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = DocumentPipeline(
            ocr_engine=TesseractEngine(),
            ner_engine=SpacyNerEngine(),
            relation_extractor=RuleBasedRelationExtractor(),
            clause_detector=RegexClauseDetector(),
            metadata_extractor=PdfMetadataExtractor(),
            chunker=SentenceWindowChunker(),
            config=OrchestratorConfig(
                run_ocr=False,
                run_layout_analysis=False,
                run_ner=True,
                run_relation_extraction=True,
                run_clause_detection=True,
                run_metadata_extraction=True,
                run_chunking=True,
            ),
        )
    return _default_pipeline


async def process_ingested_document(
    file_path: str,
    extracted_text: str | None = None,
    doc_id: str = "",
) -> dict | None:
    """Run Document Intelligence analysis on an ingestion-processed document.

    Args:
        file_path: Path to the original PDF/document file.
        extracted_text: Pre-extracted text (avoids re-reading the PDF).
        doc_id: External document identifier for tracking.

    Returns:
        Summary dict with entity/clause/chunk counts, or None on failure.
    """
    try:
        if extracted_text:
            pipeline = DocumentPipeline(
                ocr_engine=TesseractEngine(),
                ner_engine=SpacyNerEngine(),
                relation_extractor=RuleBasedRelationExtractor(),
                clause_detector=RegexClauseDetector(),
                metadata_extractor=TextMetadataExtractor(),
                chunker=SentenceWindowChunker(),
                config=OrchestratorConfig(
                    run_ocr=False,
                    run_layout_analysis=False,
                    run_ner=True,
                    run_relation_extraction=True,
                    run_clause_detection=True,
                    run_metadata_extraction=True,
                    run_chunking=True,
                ),
            )
        else:
            pipeline = _get_pipeline()

        result = await pipeline.run(Path(file_path), doc_id=doc_id)

        return {
            "doc_id": doc_id,
            "stage": result.stage.value,
            "num_entities": len(result.ner_result.entities) if result.ner_result else 0,
            "num_relations": len(result.relation_result.relations) if result.relation_result else 0,
            "num_clauses": len(result.clause_result.clauses) if result.clause_result else 0,
            "num_chunks": len(result.chunking_result.chunks) if result.chunking_result else 0,
            "errors": result.errors,
        }
    except Exception as exc:
        logger.exception("DocIntel post-processing failed for %s: %s", file_path, exc)
        return None
