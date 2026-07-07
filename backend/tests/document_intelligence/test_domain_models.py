from __future__ import annotations

from uuid import uuid4

from regulaforge.document_intelligence.domain.models import (
    EntityType,
)
from regulaforge.document_intelligence.application.models import (
    BoundingBox,
    ClassificationResult,
    ConfidenceScore,
    DocumentElement,
    ExtractedEntity,
    FormElement,
    FormField,
    PipelineResult,
    Relation,
    SemanticMetadata,
    TableCell,
    TableElement,
    TextChunk,
)
from regulaforge.document_intelligence.application.enums import (
    ClassificationLabel,
    ElementType,
    RelationType,
    ProcessingStatus,
)
from regulaforge.document_intelligence.domain.enums import (
    DocumentType,
)


class TestConfidenceScore:
    def test_clamps_value(self) -> None:
        assert ConfidenceScore(value=1.5, model="test").value == 1.0
        assert ConfidenceScore(value=-0.5, model="test").value == 0.0

    def test_level_very_high(self) -> None:
        assert ConfidenceScore(value=0.96, model="test").level == "very_high"

    def test_level_high(self) -> None:
        assert ConfidenceScore(value=0.88, model="test").level == "high"

    def test_level_medium(self) -> None:
        assert ConfidenceScore(value=0.75, model="test").level == "medium"

    def test_level_low(self) -> None:
        assert ConfidenceScore(value=0.60, model="test").level == "low"

    def test_level_very_low(self) -> None:
        assert ConfidenceScore(value=0.30, model="test").level == "very_low"


class TestTableElement:
    def test_empty_table(self) -> None:
        t = TableElement(id=uuid4(), page=1)
        assert t.num_rows() == 0
        assert t.num_cols() == 0
        assert t.to_markdown() == ""

    def test_table_with_data(self) -> None:
        t = TableElement(
            id=uuid4(),
            page=1,
            headers=["Name", "Age"],
            rows=[
                [TableCell(text="Alice", row=0, col=0), TableCell(text="30", row=0, col=1)],
                [TableCell(text="Bob", row=1, col=0), TableCell(text="25", row=1, col=1)],
            ],
            caption="Test Table",
        )
        assert t.num_rows() == 2
        assert t.num_cols() == 2
        md = t.to_markdown()
        assert "Test Table" in md
        assert "Alice" in md
        assert "Bob" in md


class TestPipelineResult:
    def test_default_status(self) -> None:
        r = PipelineResult(source_path="/test.pdf")
        assert r.status == ProcessingStatus.PENDING
        assert r.pipeline_version == "2.0.0"

    def test_to_dict_includes_counts(self) -> None:
        r = PipelineResult(source_path="/test.pdf")
        d = r.to_dict()
        assert d["source_path"] == "/test.pdf"
        assert d["elements"] == []
        assert d["tables"] == 0
        assert d["chunks"] == 0

    def test_merge(self) -> None:
        r1 = PipelineResult(source_path="/a.pdf")
        r2 = PipelineResult(source_path="/b.pdf")
        r2.entities.append(ExtractedEntity(
            id=uuid4(), entity_type=EntityType.ORGANIZATION, text="RBI",
            start_char=0, end_char=3, page=1,
            confidence=ConfidenceScore(value=0.9, model="test"),
        ))
        r1.merge(r2)
        assert len(r1.entities) == 1


class TestBoundingBox:
    def test_creation(self) -> None:
        b = BoundingBox(page=1, left=10, top=20, width=100, height=50)
        assert b.page == 1
        assert b.left == 10
        assert b.confidence == 1.0


class TestFormField:
    def test_defaults(self) -> None:
        f = FormField(label="Name")
        assert f.field_type == "text"
        assert f.value is None
        assert f.confidence == 1.0


class TestTextChunk:
    def test_creation(self) -> None:
        c = TextChunk(
            id=uuid4(), text="Hello world", page=1, chunk_index=0,
            start_char=0, end_char=11,
            tokens=2,
        )
        assert c.text == "Hello world"
        assert c.tokens == 2


class TestSemanticMetadata:
    def test_defaults(self) -> None:
        m = SemanticMetadata()
        assert m.authors == []
        assert m.keywords == []
        assert m.word_count == 0

    def test_with_data(self) -> None:
        m = SemanticMetadata(
            title="Test",
            authors=["Author One"],
            page_count=10,
            word_count=500,
            language="en",
        )
        assert m.title == "Test"
        assert m.authors == ["Author One"]


class TestDocumentElement:
    def test_creation(self) -> None:
        e = DocumentElement(
            id=uuid4(),
            element_type=ElementType.HEADER,
            text="Page Header",
            page=1,
        )
        assert e.element_type == ElementType.HEADER
        assert e.children == []
