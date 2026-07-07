"""
RegulaForge Document Intelligence Platform.

Enterprise-grade document understanding pipeline supporting:
  - Native & scanned PDF, images
  - OCR (Tesseract, PaddleOCR)
  - Layout analysis (LayoutLMv3, Docling)
  - NER, Relation Extraction, Clause Detection
  - Semantic Chunking
  - Full confidence scoring, metadata extraction, evaluation
"""

from regulaforge.document_intelligence.domain.models import (
    BoundingBox,
    DocumentElement,
    DocumentImage,
    DocumentPage,
    ExtractedEntity,
    ExtractedRelation,
    IdentifiedClause,
    PageLayout,
    ProcessedDocument,
    SemanticChunk,
    TextElement,
)
from regulaforge.document_intelligence.domain.enums import (
    DocumentType,
    ElementCategory,
    EntityType,
    ClauseType,
    ProcessingStage,
)
from regulaforge.document_intelligence.pipeline.orchestrator import DocumentPipeline

__all__ = [
    "BoundingBox",
    "DocumentElement",
    "DocumentImage",
    "DocumentPage",
    "ExtractedEntity",
    "ExtractedRelation",
    "IdentifiedClause",
    "PageLayout",
    "ProcessedDocument",
    "SemanticChunk",
    "TextElement",
    "DocumentType",
    "ElementCategory",
    "EntityType",
    "ClauseType",
    "ProcessingStage",
    "DocumentPipeline",
]
