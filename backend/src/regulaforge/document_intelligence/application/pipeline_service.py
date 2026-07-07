from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from regulaforge.document_intelligence.application.chunking_service import ChunkingService
from regulaforge.document_intelligence.application.classification_service import ClassificationService
from regulaforge.document_intelligence.application.metadata_service import MetadataService
from regulaforge.document_intelligence.application.ner_service import NERService
from regulaforge.document_intelligence.application.ocr_service import OCRService
from regulaforge.document_intelligence.application.relation_extraction import RelationExtractionService
from regulaforge.document_intelligence.application.table_extraction import TableExtractionService
from regulaforge.document_intelligence.application.enums import ProcessingStatus
from regulaforge.document_intelligence.application.models import PipelineResult, SemanticMetadata
from regulaforge.document_intelligence.domain.enums import DocumentType
from regulaforge.document_intelligence.infrastructure.layout.layout_analyzer import LayoutAnalyzer
from regulaforge.document_intelligence.infrastructure.pdf.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


class DocumentIntelligencePipeline:
    def __init__(
        self,
        pdf_processor: PDFProcessor,
        ocr_service: OCRService,
        layout_analyzer: LayoutAnalyzer,
        ner_service: NERService,
        classification_service: ClassificationService,
        chunking_service: ChunkingService,
        table_extraction: TableExtractionService,
        relation_extraction: RelationExtractionService,
        metadata_service: MetadataService,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._pdf = pdf_processor
        self._ocr = ocr_service
        self._layout = layout_analyzer
        self._ner = ner_service
        self._classifier = classification_service
        self._chunker = chunking_service
        self._tables = table_extraction
        self._relations = relation_extraction
        self._metadata = metadata_service
        self._confidence_threshold = confidence_threshold

    async def process(
        self,
        source_path: str,
        document_id: UUID | None = None,
        document_type: DocumentType | None = None,
        extract_tables: bool = True,
        extract_clauses: bool = True,
        extract_forms: bool = True,
        extract_lists: bool = True,
        run_ner: bool = True,
        run_classification: bool = True,
        run_chunking: bool = True,
        run_relations: bool = True,
        ocr_fallback: bool = True,
    ) -> PipelineResult:
        start_time = time.time()
        result = PipelineResult(
            id=uuid4(),
            document_id=document_id or uuid4(),
            source_path=source_path,
            status=ProcessingStatus.PENDING,
        )
        logger.info("Pipeline started: %s", source_path)

        try:
            doc_type = document_type or self._detect_type(source_path)
            result.document_type = doc_type

            text, pages_images = await self._load_document(source_path, doc_type)
            result.raw_text = text

            if not text.strip() and ocr_fallback:
                result.status = ProcessingStatus.OCR_REQUIRED
                text = await self._ocr.process(pages_images if pages_images else [source_path])
                result.raw_text = text
                result.metadata = result.metadata or SemanticMetadata()
                result.metadata.is_scanned = True

            result.status = ProcessingStatus.LAYOUT_ANALYSIS
            elements = await self._layout.analyze(source_path, text)
            result.elements = elements

            if extract_tables:
                tables = await self._tables.extract(source_path, elements)
                result.tables = tables

            if extract_clauses:
                clauses = self._extract_clauses(text, elements)
                result.clauses = clauses

            if extract_forms:
                forms = self._extract_forms(elements)
                result.forms = forms

            if extract_lists:
                lists = self._extract_lists(elements, text)
                result.lists = lists

            if run_ner:
                result.status = ProcessingStatus.NER_IN_PROGRESS
                entities = await self._ner.extract(text, elements)
                result.entities = entities

            if run_classification:
                result.status = ProcessingStatus.CLASSIFYING
                classification = await self._classifier.classify(text, result.metadata)
                result.classification = classification

            if run_relations and run_ner and result.entities:
                relations = await self._relations.extract(result.entities, text)
                result.relations = relations

            if run_chunking:
                result.status = ProcessingStatus.CHUNKING
                chunks = await self._chunker.chunk(text, elements, result.entities)
                result.chunks = chunks

            meta = await self._metadata.generate(
                text=text,
                elements=elements,
                entities=result.entities,
                tables=result.tables,
                classification=result.classification,
                source_path=source_path,
            )
            result.metadata = meta

            result.status = ProcessingStatus.COMPLETED

        except Exception as exc:
            logger.exception("Pipeline failed for %s", source_path)
            result.status = ProcessingStatus.FAILED
            result.error_message = str(exc)

        result.processing_time_ms = (time.time() - start_time) * 1000
        logger.info(
            "Pipeline finished: status=%s, time=%.0fms, elements=%d, entities=%d, chunks=%d",
            result.status.value,
            result.processing_time_ms,
            len(result.elements),
            len(result.entities),
            len(result.chunks),
        )
        return result

    def _detect_type(self, path: str) -> DocumentType:
        ext = Path(path).suffix.lower()
        if ext == ".pdf":
            return DocumentType.NATIVE_PDF
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
            return DocumentType.IMAGE
        if ext == ".docx":
            return DocumentType.DOCX
        if ext == ".html":
            return DocumentType.HTML
        if ext in (".txt", ".md"):
            return DocumentType.TEXT
        return DocumentType.NATIVE_PDF

    async def _load_document(self, path: str, doc_type: DocumentType) -> tuple[str, list[str]]:
        if doc_type in (DocumentType.NATIVE_PDF, DocumentType.SCANNED_PDF):
            return await self._pdf.extract_text(path)
        if doc_type == DocumentType.IMAGE:
            return "", [path]
        if doc_type == DocumentType.TEXT:
            text = Path(path).read_text(encoding="utf-8")
            return text, []
        return "", []

    def _extract_clauses(self, text: str, elements: list[Any]) -> list[Any]:
        import re
        from uuid import uuid4

        from regulaforge.document_intelligence.application.enums import ElementType
        from regulaforge.document_intelligence.application.models import Clause, ConfidenceScore

        clauses: list[Any] = []
        clause_patterns = [
            r"(Clause\s+\d+[.\d]*)\s*[-–—]?\s*(.*?)(?=\n\s*(?:Clause\s+\d+|$))",
            r"(Section\s+\d+[.\d]*)\s*[-–—]?\s*(.*?)(?=\n\s*(?:Section\s+\d+|$))",
            r"(Article\s+\d+[.\d]*)\s*[-–—]?\s*(.*?)(?=\n\s*(?:Article\s+\d+|$))",
            r"(Para\s+\d+[.\d]*)\s*[-–—]?\s*(.*?)(?=\n\s*(?:Para\s+\d+|$))",
        ]

        for pattern in clause_patterns:
            for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
                clause_id = match.group(1).strip()
                clause_text = match.group(2).strip()
                if len(clause_text) < 10:
                    continue
                clause = Clause(
                    id=str(uuid4()),
                    text=clause_text,
                    clause_id=clause_id,
                    confidence=ConfidenceScore(value=0.85, model="regex"),
                )
                clauses.append(clause)

        if not clauses:
            for elem in elements:
                if elem.element_type == ElementType.PARAGRAPH and len(elem.text) > 100:
                    clause = Clause(
                        id=str(uuid4()),
                        text=elem.text,
                        page=elem.page,
                        bbox=elem.bbox,
                        confidence=elem.confidence,
                    )
                    clauses.append(clause)

        return clauses

    def _extract_forms(self, elements: list[Any]) -> list[Any]:
        from uuid import uuid4

        from regulaforge.document_intelligence.application.models import ConfidenceScore, FormElement

        forms: list[Any] = []
        form_elements = [e for e in elements if e.element_type.value == "form"]
        if form_elements:
            for fe in form_elements:
                forms.append(
                    FormElement(
                        id=str(uuid4()),
                        page=fe.page,
                        confidence=ConfidenceScore(value=0.7, model="layout"),
                    )
                )
        return forms

    def _extract_lists(self, _elements: list[Any], text: str) -> list[Any]:
        import re

        from regulaforge.document_intelligence.application.models import ListItem

        items: list[Any] = []
        lines = text.split("\n")
        for _i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r"^[\d]+[.)]\s", stripped):
                items.append(ListItem(text=stripped, level=0, ordinal=stripped.split(".")[0], page=0))
            elif re.match(r"^[a-zA-Z][.)]\s", stripped):
                items.append(ListItem(text=stripped, level=1, ordinal=stripped[0], page=0))
            elif stripped.startswith("- ") or stripped.startswith("* "):  # noqa: SIM114
                items.append(ListItem(text=stripped[2:], level=2, page=0))
            elif stripped.startswith("• "):
                items.append(ListItem(text=stripped[2:], level=2, page=0))
        return items
