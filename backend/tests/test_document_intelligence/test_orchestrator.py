"""Tests for the document processing pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulaforge.document_intelligence.chunking.semantic_chunker import SentenceWindowChunker
from regulaforge.document_intelligence.domain.enums import ClauseType, ElementCategory, EntityType, ProcessingStage
from regulaforge.document_intelligence.domain.models import (
    BoundingBox,
    DocumentElement,
    ExtractedEntity,
    ExtractedRelation,
    IdentifiedClause,
    PageLayout,
    SemanticChunk,
)
from regulaforge.document_intelligence.extraction.clauses import ClauseResult, RegexClauseDetector
from regulaforge.document_intelligence.extraction.metadata import MetadataResult, TextMetadataExtractor
from regulaforge.document_intelligence.extraction.ner import NerResult, SpacyNerEngine
from regulaforge.document_intelligence.extraction.relations import RelationResult, RuleBasedRelationExtractor
from regulaforge.document_intelligence.layout.base import LayoutAnalyzer, LayoutResult
from regulaforge.document_intelligence.ocr.base import OcrEngine, OcrPageResult, OcrResult, OcrWord
from regulaforge.document_intelligence.pipeline.orchestrator import (
    DocumentPipeline,
    OrchestratorConfig,
    PipelineResult,
)


class FakeOcrEngine(OcrEngine):
    @property
    def name(self) -> str:
        return "fake-ocr"

    async def is_available(self) -> bool:
        return True

    async def recognize(self, image_path: Path, **kwargs: object) -> OcrPageResult:
        return OcrPageResult(page_number=1, text="test", confidence=0.9)

    async def recognize_multi(self, image_paths: list[Path], **kwargs: object) -> OcrResult:
        pages = [await self.recognize(p, page_number=i + 1) for i, p in enumerate(image_paths)]
        return OcrResult(
            pages=pages,
            full_text=" ".join(p.text for p in pages),
            overall_confidence=0.9,
        )


class FakeLayoutAnalyzer(LayoutAnalyzer):
    @property
    def name(self) -> str:
        return "fake-layout"

    async def is_available(self) -> bool:
        return True

    async def analyze_page(self, image_path: Path, page_number: int = 1, **kwargs: object) -> PageLayout:
        return PageLayout(
            page_number=page_number, width=612, height=792,
            elements=[DocumentElement(id="el-1", category=ElementCategory.PARAGRAPH, bbox=BoundingBox(0, 0, 100, 50))],
            confidence=0.9,
        )

    async def analyze(self, image_paths: list[Path], **kwargs: object) -> LayoutResult:
        pages = [await self.analyze_page(p, page_number=i + 1) for i, p in enumerate(image_paths)]
        return LayoutResult(pages=pages, overall_confidence=0.9, num_pages=len(pages))


class FakeNerEngine(SpacyNerEngine):
    def __init__(self) -> None:
        super().__init__()
        self._available = True

    async def is_available(self) -> bool:
        return True

    async def extract(self, text: str, **kwargs: object) -> NerResult:
        return NerResult(
            entities=[
                ExtractedEntity(type=EntityType.ORGANIZATION, text="RBI", confidence=0.9),
            ],
            overall_confidence=0.9,
        )

    def _load(self) -> None:
        pass


class FakeRelationExtractor(RuleBasedRelationExtractor):
    async def extract(self, entities: list, text: str, **kwargs: object) -> RelationResult:
        return RelationResult(
            relations=[
                ExtractedRelation(
                    source_id="ent-1", target_id="ent-2",
                    relation_type="ISSUES", confidence=0.8,
                ),
            ],
            overall_confidence=0.8,
        )


class FakeClauseDetector(RegexClauseDetector):
    async def detect(self, text: str, **kwargs: object) -> ClauseResult:
        return ClauseResult(
            clauses=[
                IdentifiedClause(type=ClauseType.OBLIGATION, text="shall comply", confidence=0.85),
            ],
            overall_confidence=0.85,
        )

    def _compile(self) -> None:
        pass


@pytest.mark.asyncio
async def test_pipeline_empty_config():
    pipeline = DocumentPipeline(config=OrchestratorConfig(
        run_ocr=False, run_layout_analysis=False, run_ner=False,
        run_relation_extraction=False, run_clause_detection=False,
        run_metadata_extraction=False, run_chunking=False,
    ))
    result = await pipeline.run(Path("/fake.pdf"))
    assert result.stage == ProcessingStage.COMPLETE


@pytest.mark.asyncio
async def test_pipeline_ocr_only():
    pipeline = DocumentPipeline(
        ocr_engine=FakeOcrEngine(),
        config=OrchestratorConfig(
            run_ocr=True, run_layout_analysis=False, run_ner=False,
            run_relation_extraction=False, run_clause_detection=False,
            run_metadata_extraction=False, run_chunking=False,
        ),
    )
    result = await pipeline.run(Path("/fake.pdf"))
    assert result.ocr_result is not None
    assert result.ocr_result.overall_confidence == 0.9


@pytest.mark.asyncio
async def test_pipeline_full():
    pipeline = DocumentPipeline(
        ocr_engine=FakeOcrEngine(),
        layout_analyzer=FakeLayoutAnalyzer(),
        ner_engine=FakeNerEngine(),
        relation_extractor=FakeRelationExtractor(),
        clause_detector=FakeClauseDetector(),
        metadata_extractor=TextMetadataExtractor(),
        chunker=SentenceWindowChunker(chunk_size=5),
        config=OrchestratorConfig(
            run_ocr=True, run_layout_analysis=True, run_ner=True,
            run_relation_extraction=True, run_clause_detection=True,
            run_metadata_extraction=True, run_chunking=True,
        ),
    )
    result = await pipeline.run(Path("/fake.pdf"))
    assert result.stage == ProcessingStage.COMPLETE
    assert result.ocr_result is not None
    assert result.layout_result is not None
    assert result.ner_result is not None and len(result.ner_result.entities) > 0
    assert result.relation_result is not None and len(result.relation_result.relations) > 0
    assert result.clause_result is not None and len(result.clause_result.clauses) > 0
    assert result.chunking_result is not None and result.chunking_result.num_chunks > 0
    assert result.document is not None


@pytest.mark.asyncio
async def test_pipeline_propagates_errors():
    class BrokenOcr(FakeOcrEngine):
        async def recognize_multi(self, image_paths: list[Path], **kwargs: object) -> OcrResult:
            raise RuntimeError("OCR failed")

    pipeline = DocumentPipeline(
        ocr_engine=BrokenOcr(),
        config=OrchestratorConfig(run_ocr=True),
    )
    result = await pipeline.run(Path("/fake.pdf"))
    assert result.stage == ProcessingStage.FAILED
    assert "pipeline" in result.errors


@pytest.mark.asyncio
async def test_pipeline_handles_unavailable_engine():
    class UnavailableNer(SpacyNerEngine):
        async def is_available(self) -> bool:
            return False

    pipeline = DocumentPipeline(
        ocr_engine=FakeOcrEngine(),
        ner_engine=UnavailableNer(),
        config=OrchestratorConfig(run_ocr=True, run_ner=True),
    )
    result = await pipeline.run(Path("/fake.pdf"), image_paths=[Path("/fake.png")])
    assert "ner" in result.errors
    assert result.ocr_result is not None  # OCR should still work


@pytest.mark.asyncio
async def test_pipeline_builds_document():
    pipeline = DocumentPipeline(
        ocr_engine=FakeOcrEngine(),
        ner_engine=FakeNerEngine(),
        config=OrchestratorConfig(run_ocr=True, run_ner=True),
    )
    result = await pipeline.run(Path("/fake.pdf"), image_paths=[Path("/fake.png")], doc_id="doc-123")
    assert result.document is not None
    assert result.document.id == "doc-123"
    assert len(result.document.entities) > 0
