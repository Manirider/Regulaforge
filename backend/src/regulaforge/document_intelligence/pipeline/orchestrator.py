"""
Document processing pipeline orchestrator.

Coordinates the full workflow:
  1. OCR (Tesseract / PaddleOCR)
  2. Layout analysis (LayoutLMv3 / Docling)
  3. NER (spaCy / HuggingFace)
  4. Relation extraction (rule-based)
  5. Clause detection (regex)
  6. Metadata extraction
  7. Semantic chunking

Long-running I/O (PDF rendering, Docling conversion) is offloaded
to a thread executor to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from regulaforge.document_intelligence.chunking.semantic_chunker import (
    SemanticChunker,
    SemanticChunkingResult,
)
from regulaforge.document_intelligence.domain.enums import ProcessingStage
from regulaforge.document_intelligence.domain.models import (
    DocumentPage,
    ProcessedDocument,
)
from regulaforge.document_intelligence.extraction.clauses import ClauseDetector, ClauseResult
from regulaforge.document_intelligence.extraction.metadata import MetadataExtractor, MetadataResult
from regulaforge.document_intelligence.extraction.ner import NerEngine, NerResult
from regulaforge.document_intelligence.extraction.relations import RelationExtractor, RelationResult
from regulaforge.document_intelligence.layout.base import LayoutAnalyzer, LayoutResult
from regulaforge.document_intelligence.ocr.base import OcrEngine, OcrResult

async def _run_blocking(fn: Any, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


@dataclass
class OrchestratorConfig:
    run_ocr: bool = True
    run_layout_analysis: bool = True
    run_ner: bool = True
    run_relation_extraction: bool = True
    run_clause_detection: bool = True
    run_metadata_extraction: bool = True
    run_chunking: bool = True
    chunking_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    document: ProcessedDocument | None = None
    ocr_result: OcrResult | None = None
    layout_result: LayoutResult | None = None
    ner_result: NerResult | None = None
    relation_result: RelationResult | None = None
    clause_result: ClauseResult | None = None
    metadata_result: MetadataResult | None = None
    chunking_result: SemanticChunkingResult | None = None
    errors: dict[str, str] = field(default_factory=dict)
    stage: ProcessingStage = ProcessingStage.LOADED


class DocumentPipeline:
    """Configurable pipeline for end-to-end document processing.

    Args:
        ocr_engine: The OCR engine to use.
        layout_analyzer: The layout analysis engine.
        ner_engine: The named entity recognition engine.
        relation_extractor: The relation extraction engine.
        clause_detector: The clause detection engine.
        metadata_extractor: The metadata extraction engine.
        chunker: The semantic chunking engine.
        config: Pipeline configuration flags.
    """

    def __init__(
        self,
        ocr_engine: OcrEngine | None = None,
        layout_analyzer: LayoutAnalyzer | None = None,
        ner_engine: NerEngine | None = None,
        relation_extractor: RelationExtractor | None = None,
        clause_detector: ClauseDetector | None = None,
        metadata_extractor: MetadataExtractor | None = None,
        chunker: SemanticChunker | None = None,
        config: OrchestratorConfig | None = None,
    ) -> None:
        self._ocr = ocr_engine
        self._layout = layout_analyzer
        self._ner = ner_engine
        self._relations = relation_extractor
        self._clauses = clause_detector
        self._metadata = metadata_extractor
        self._chunker = chunker
        self._config = config or OrchestratorConfig()

    @property
    def config(self) -> OrchestratorConfig:
        return self._config

    @config.setter
    def config(self, value: OrchestratorConfig) -> None:
        self._config = value

    async def run(
        self,
        file_path: Path,
        image_paths: list[Path] | None = None,
        **kwargs: Any,
    ) -> PipelineResult:
        """Process a single document through the configured pipeline stages.

        Args:
            file_path: Path to the input document.
            image_paths: Optional pre-rendered page images (for scanned PDFs).
            kwargs: Additional keyword arguments forwarded to each stage.

        Returns:
            A ``PipelineResult`` containing all stage outputs.
        """
        result = PipelineResult()
        ocr_text: str = ""

        try:
            if self._config.run_metadata_extraction and self._metadata:
                if await self._metadata.is_available():
                    result.metadata_result = await self._metadata.extract(
                        file_path, text=None, **kwargs
                    )

            if self._config.run_ocr and self._ocr:
                if not await self._ocr.is_available():
                    result.errors["ocr"] = "OCR engine not available"
                else:
                    pages = image_paths or await _run_blocking(
                        self._render_pages, file_path
                    )
                    result.ocr_result = await self._ocr.recognize_multi(
                        pages, **kwargs
                    )
                    ocr_text = result.ocr_result.full_text
                    result.stage = ProcessingStage.OCR_COMPLETE

            if self._config.run_layout_analysis and self._layout:
                if not await self._layout.is_available():
                    result.errors["layout"] = "Layout analyzer not available"
                else:
                    pages = image_paths or await _run_blocking(
                        self._render_pages, file_path
                    )
                    result.layout_result = await self._layout.analyze(
                        pages, **kwargs
                    )
                    result.stage = ProcessingStage.LAYOUT_ANALYZED

            if self._config.run_ner and self._ner and ocr_text:
                if not await self._ner.is_available():
                    result.errors["ner"] = "NER engine not available"
                else:
                    result.ner_result = await self._ner.extract(ocr_text, **kwargs)
                    result.stage = ProcessingStage.ENTITIES_EXTRACTED

            if self._config.run_relation_extraction and self._relations and result.ner_result:
                if not await self._relations.is_available():
                    result.errors["relations"] = "Relation extractor not available"
                else:
                    result.relation_result = await self._relations.extract(
                        result.ner_result.entities, ocr_text, **kwargs
                    )
                    result.stage = ProcessingStage.RELATIONS_EXTRACTED

            if self._config.run_clause_detection and self._clauses and ocr_text:
                if not await self._clauses.is_available():
                    result.errors["clauses"] = "Clause detector not available"
                else:
                    result.clause_result = await self._clauses.detect(
                        ocr_text, **kwargs
                    )
                    result.stage = ProcessingStage.CLAUSES_IDENTIFIED

            if self._config.run_chunking and self._chunker and ocr_text:
                if not await self._chunker.is_available():
                    result.errors["chunking"] = "Chunker not available"
                else:
                    chunk_kwargs = {**self._config.chunking_kwargs, **kwargs}
                    result.chunking_result = await self._chunker.chunk(
                        ocr_text, **chunk_kwargs
                    )
                    result.stage = ProcessingStage.CHUNKED

            pages: list[DocumentPage] = []
            num_pages = len(result.ocr_result.pages) if result.ocr_result else 1
            for i in range(num_pages):
                page_layout = (
                    result.layout_result.pages[i]
                    if result.layout_result and i < len(result.layout_result.pages)
                    else None
                )
                page_text = (
                    result.ocr_result.pages[i].text
                    if result.ocr_result and i < len(result.ocr_result.pages)
                    else ocr_text
                )
                pages.append(
                    DocumentPage(
                        page_number=i + 1,
                        text=page_text,
                        layout=page_layout,
                        ocr_confidence=(
                            result.ocr_result.pages[i].confidence
                            if result.ocr_result and i < len(result.ocr_result.pages)
                            else 0.0
                        ),
                    )
                )

            result.document = ProcessedDocument(
                id=kwargs.get("doc_id", str(hash(file_path))),
                source_path=file_path,
                pages=pages,
                entities=result.ner_result.entities if result.ner_result else [],
                relations=result.relation_result.relations if result.relation_result else [],
                clauses=result.clause_result.clauses if result.clause_result else [],
                chunks=result.chunking_result.chunks if result.chunking_result else [],
                metadata=(
                    ProcessedDocument._format_metadata(result.metadata_result)
                    if result.metadata_result
                    else {}
                ),
                stage=result.stage,
            )

            result.stage = ProcessingStage.COMPLETE

        except Exception as exc:
            result.errors["pipeline"] = f"{type(exc).__name__}: {exc}"
            result.stage = ProcessingStage.FAILED

        return result

    @staticmethod
    def _render_pages(file_path: Path) -> list[Path]:
        if file_path.suffix.lower() == ".pdf":
            try:
                import fitz
                doc = fitz.open(str(file_path))
                paths: list[Path] = []
                for i in range(doc.page_count):
                    pix = doc[i].get_pixmap(dpi=200)
                    temp = file_path.parent / f"{file_path.stem}_page_{i + 1}.png"
                    pix.save(str(temp))
                    paths.append(temp)
                doc.close()
                return paths
            except ImportError:
                logger.warning(
                    "PyMuPDF not available; cannot render PDF pages. "
                    "Install with: pip install pymupdf"
                )
        return [file_path]
