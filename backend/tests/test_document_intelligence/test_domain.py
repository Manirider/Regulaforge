"""Tests for domain models and enums."""

from __future__ import annotations

from regulaforge.document_intelligence.domain.enums import (
    ClauseType, DocumentType, ElementCategory, EntityType, ProcessingStage,
)
from regulaforge.document_intelligence.domain.models import (
    BoundingBox, DocumentElement, DocumentImage, DocumentPage,
    ExtractedEntity, ExtractedRelation, IdentifiedClause, PageLayout,
    ProcessedDocument, SemanticChunk, TextElement,
)


def test_bounding_box():
    bb = BoundingBox(x0=1.0, y0=2.0, x1=3.0, y1=4.0)
    assert bb.x0 == 1.0
    assert bb.y0 == 2.0
    assert bb.x1 == 3.0
    assert bb.y1 == 4.0
    assert bb.width == 2.0
    assert bb.height == 2.0


def test_bounding_box_zero_area():
    bb = BoundingBox(x0=0.0, y0=0.0, x1=0.0, y1=0.0)
    assert bb.area == 0.0


def test_text_element():
    el = TextElement(
        id="t1", text="Hello", confidence=0.95,
        bbox=BoundingBox(0, 0, 10, 10),
    )
    assert el.id == "t1"
    assert el.text == "Hello"
    assert el.confidence == 0.95


def test_extracted_entity_default_id():
    e = ExtractedEntity(
        type=EntityType.ORGANIZATION, text="RBI", confidence=0.9,
    )
    assert e.id is not None


def test_semantic_chunk_defaults():
    c = SemanticChunk(text="some text")
    assert c.id is not None
    assert c.page_number == 0
    assert c.confidence == 0.0


def test_element_category_values():
    assert ElementCategory.PARAGRAPH.value == "paragraph"
    assert ElementCategory.TABLE.value == "table"
    assert ElementCategory.HEADING.value == "heading"


def test_entity_type_values():
    assert EntityType.ORGANIZATION.value == "organization"
    assert EntityType.REGULATION_ID.value == "regulation_id"


def test_clause_type_values():
    assert ClauseType.OBLIGATION.value == "obligation"
    assert ClauseType.DEFINITION.value == "definition"


def test_processing_stage_order():
    stages = list(ProcessingStage)
    assert stages.index(ProcessingStage.LOADED) < stages.index(ProcessingStage.OCR_COMPLETE)
    assert stages.index(ProcessingStage.OCR_COMPLETE) < stages.index(ProcessingStage.LAYOUT_ANALYZED)
    assert stages[-2] == ProcessingStage.COMPLETE
    assert stages[-1] == ProcessingStage.FAILED


def test_document_type_values():
    assert DocumentType.NATIVE_PDF.value == "native_pdf"
    assert DocumentType.SCANNED_PDF.value == "scanned_pdf"
    assert DocumentType.IMAGE.value == "image"


def test_document_element_abstract():
    import dataclasses
    assert dataclasses.is_dataclass(DocumentElement)


def test_document_image():
    img = DocumentImage(path="/tmp/test.png", page_number=1)
    assert img.path == "/tmp/test.png"
    assert img.page_number == 1
    assert img.confidence == 1.0


def test_document_page():
    page = DocumentPage(page_number=1, width=612.0, height=792.0)
    assert page.page_number == 1
    assert page.elements == []


def test_page_layout():
    layout = PageLayout(page_number=1, width=612.0, height=792.0)
    assert layout.elements == []


def test_extracted_entity_with_metadata():
    e = ExtractedEntity(
        type=EntityType.AMOUNT,
        text="₹10,00,000",
        confidence=0.95,
        metadata={"currency": "INR"},
    )
    assert e.metadata["currency"] == "INR"


def test_extracted_relation():
    r = ExtractedRelation(
        source_id="ent-1", target_id="ent-2",
        relation_type="ISSUES", confidence=0.8,
    )
    assert r.source_id == "ent-1"
    assert r.target_id == "ent-2"


def test_identified_clause():
    c = IdentifiedClause(
        type=ClauseType.PENALTY, text="penalty for non-compliance",
        confidence=0.85,
    )
    assert c.clause_type == ClauseType.PENALTY
    assert "penalty" in c.text


def test_process_document_defaults():
    doc = ProcessedDocument(file_path="/tmp/doc.pdf")
    assert doc.pages == []
    assert doc.entities == []
    assert doc.relations == []
    assert doc.clauses == []
    assert doc.chunks == []
    assert doc.metadata is None
