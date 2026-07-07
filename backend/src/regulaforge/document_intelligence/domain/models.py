"""
Core domain models for the Document Intelligence pipeline.

Every extraction result carries a ``confidence`` score in [0.0, 1.0]
to enable downstream threshold-based filtering and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from regulaforge.document_intelligence.domain.enums import (
    ClauseType,
    DocumentType,
    ElementCategory,
    EntityType,
    ProcessingStage,
)


@dataclass(frozen=True)
class BoundingBox:
    """Normalised bounding box (coordinates in [0, 1] relative to page)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    def overlaps(self, other: BoundingBox, threshold: float = 0.5) -> bool:
        ix0 = max(self.x0, other.x0)
        iy0 = max(self.y0, other.y0)
        ix1 = min(self.x1, other.x1)
        iy1 = min(self.y1, other.y1)
        intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
        union = self.area + other.area - intersection
        return union > 0 and intersection / union >= threshold


@dataclass
class DocumentElement:
    """A single visual/textual element detected on a page.

    Attributes:
        id: Unique element identifier.
        category: Semantic category (paragraph, table, header, …).
        text: Extracted text content (empty for non-text elements).
        bbox: Normalised bounding box.
        confidence: Model confidence for this element.
        metadata: Extensible key-value metadata.
    """

    id: str
    category: ElementCategory = ElementCategory.PARAGRAPH
    text: str = ""
    bbox: BoundingBox | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "text": self.text,
            "bbox": {"x0": self.bbox.x0, "y0": self.bbox.y0, "x1": self.bbox.x1, "y1": self.bbox.y1}
            if self.bbox
            else None,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class TextElement(DocumentElement):
    """Text-specific element with formatting hints."""

    font_size: float | None = None
    font_family: str | None = None
    is_bold: bool = False
    is_italic: bool = False
    is_underlined: bool = False
    text_color: str | None = None


@dataclass
class TableCell:
    text: str = ""
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    confidence: float = 1.0


@dataclass
class TableElement(DocumentElement):
    rows: int = 0
    cols: int = 0
    cells: list[list[TableCell]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.category = ElementCategory.TABLE

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["rows"] = self.rows
        base["cols"] = self.cols
        base["cells"] = [
            [{"text": c.text, "is_header": c.is_header, "confidence": c.confidence} for c in row]
            for row in self.cells
        ]
        return base


@dataclass
class PageLayout:
    """Layout structure for a single page."""

    page_number: int
    width: float
    height: float
    elements: list[DocumentElement] = field(default_factory=list)
    confidence: float = 1.0

    def by_category(self, category: ElementCategory) -> list[DocumentElement]:
        return [e for e in self.elements if e.category == category]

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "elements": [e.to_dict() for e in self.elements],
            "confidence": self.confidence,
        }


@dataclass
class DocumentPage:
    """A single page within a document."""

    page_number: int
    text: str = ""
    layout: PageLayout | None = None
    image_path: Path | None = None
    ocr_confidence: float = 0.0
    width: float = 0.0
    height: float = 0.0
    elements: list[DocumentElement] = field(default_factory=list)


@dataclass
class DocumentImage:
    """Represents a loaded document page as an image for OCR."""

    page_number: int
    width: int = 0
    height: int = 0
    dpi: int = 300
    mode: str = "RGB"
    data: Any = None  # numpy array or PIL Image
    path: Path | None = None
    confidence: float = 1.0


@dataclass
class ExtractedEntity:
    """A named entity found in the document.

    Attributes:
        id: Unique entity identifier.
        type: Entity type (organisation, person, date, …).
        text: Extracted surface form.
        bbox: Optional bounding box on the original page.
        confidence: Extraction confidence.
        page_number: Source page (1-indexed).
        metadata: Additional entity attributes.
    """

    type: EntityType
    text: str
    id: str = field(default_factory=lambda: str(uuid4()))
    bbox: BoundingBox | None = None
    confidence: float = 1.0
    page_number: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedRelation:
    """A semantic relation between two extracted entities."""

    source_entity_id: str
    target_entity_id: str
    relation_type: str
    id: str = field(default_factory=lambda: str(uuid4()))
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        source_entity_id: str | None = None,
        target_entity_id: str | None = None,
        relation_type: str = "",
        id: str | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> None:
        self.source_entity_id = source_entity_id or source_id or ""
        self.target_entity_id = target_entity_id or target_id or ""
        self.relation_type = relation_type
        self.id = id or str(uuid4())
        self.confidence = confidence
        self.metadata = metadata if metadata is not None else {}

    @property
    def source_id(self) -> str:
        return self.source_entity_id

    @property
    def target_id(self) -> str:
        return self.target_entity_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class IdentifiedClause:
    """A detected regulatory/legal clause within the document.

    Attributes:
        id: Unique clause identifier.
        clause_type: Semantic type of clause.
        text: Full clause text.
        section_ref: Section or paragraph reference (e.g. "4(2)(a)").
        confidence: Detection confidence.
        page_number: Source page (1-indexed).
        bbox: Optional bounding box.
        metadata: Additional clause attributes.
    """

    clause_type: ClauseType
    text: str
    id: str = field(default_factory=lambda: str(uuid4()))
    section_ref: str | None = None
    confidence: float = 1.0
    page_number: int = 1
    bbox: BoundingBox | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        clause_type: ClauseType | None = None,
        text: str = "",
        id: str | None = None,
        section_ref: str | None = None,
        confidence: float = 1.0,
        page_number: int = 1,
        bbox: BoundingBox | None = None,
        metadata: dict[str, Any] | None = None,
        type: ClauseType | None = None,
    ) -> None:
        self.clause_type = clause_type or type or ClauseType.OBLIGATION
        self.text = text
        self.id = id or str(uuid4())
        self.section_ref = section_ref
        self.confidence = confidence
        self.page_number = page_number
        self.bbox = bbox
        self.metadata = metadata if metadata is not None else {}


@dataclass
class SemanticChunk:
    """A semantically coherent text chunk with metadata.

    Attributes:
        id: Unique chunk identifier.
        text: Chunk text content.
        chunk_type: Semantic type (section, paragraph, list, …).
        page_number: Source page (1-indexed).
        embedding: Optional vector embedding for retrieval.
        confidence: Chunk quality score.
        metadata: Additional chunk metadata.
    """

    text: str
    id: str = field(default_factory=lambda: str(uuid4()))
    chunk_type: str = "paragraph"
    page_number: int = 0
    bbox: BoundingBox | None = None
    embedding: list[float] | None = None
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "chunk_type": self.chunk_type,
            "page_number": self.page_number,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class ProcessedDocument:
    """The final result of the Document Intelligence pipeline.

    Aggregates layout, OCR, entities, relations, clauses, chunks, and
    metadata for a single input document.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    source_path: Path | None = None
    document_type: DocumentType = DocumentType.NATIVE_PDF
    pages: list[DocumentPage] = field(default_factory=list)
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    clauses: list[IdentifiedClause] = field(default_factory=list)
    chunks: list[SemanticChunk] = field(default_factory=list)
    metadata: dict[str, Any] | None = None
    stage: ProcessingStage = ProcessingStage.LOADED
    overall_confidence: float = 0.0
    processing_time_ms: float = 0.0
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __init__(
        self,
        id: str | None = None,
        source_path: Path | str | None = None,
        document_type: DocumentType = DocumentType.NATIVE_PDF,
        pages: list[DocumentPage] | None = None,
        entities: list[ExtractedEntity] | None = None,
        relations: list[ExtractedRelation] | None = None,
        clauses: list[IdentifiedClause] | None = None,
        chunks: list[SemanticChunk] | None = None,
        metadata: dict[str, Any] | None = None,
        stage: ProcessingStage = ProcessingStage.LOADED,
        overall_confidence: float = 0.0,
        processing_time_ms: float = 0.0,
        error: str | None = None,
        created_at: datetime | None = None,
        file_path: Path | str | None = None,
    ) -> None:
        self.id = id or str(uuid4())
        self.source_path = Path(source_path) if source_path else (Path(file_path) if file_path else None)
        self.document_type = document_type
        self.pages = pages if pages is not None else []
        self.entities = entities if entities is not None else []
        self.relations = relations if relations is not None else []
        self.clauses = clauses if clauses is not None else []
        self.chunks = chunks if chunks is not None else []
        self.metadata = metadata
        self.stage = stage
        self.overall_confidence = overall_confidence
        self.processing_time_ms = processing_time_ms
        self.error = error
        self.created_at = created_at or datetime.utcnow()

    @property
    def file_path(self) -> str | None:
        return str(self.source_path) if self.source_path else None

    @staticmethod
    def _format_metadata(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if hasattr(value, "__dataclass_fields__"):
            from dataclasses import asdict
            return asdict(value)
        return {}

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": str(self.source_path) if self.source_path else None,
            "document_type": self.document_type.value,
            "pages": len(self.pages),
            "entities": len(self.entities),
            "relations": len(self.relations),
            "clauses": len(self.clauses),
            "chunks": len(self.chunks),
            "stage": self.stage.value,
            "overall_confidence": self.overall_confidence,
            "processing_time_ms": self.processing_time_ms,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.summary(),
            "pages": [
                {
                    "page_number": p.page_number,
                    "text_length": len(p.text),
                    "ocr_confidence": p.ocr_confidence,
                    "layout": p.layout.to_dict() if p.layout else None,
                }
                for p in self.pages
            ],
            "entities": [
                {
                    "id": e.id,
                    "type": e.type.value,
                    "text": e.text,
                    "confidence": e.confidence,
                    "page_number": e.page_number,
                    "metadata": e.metadata,
                }
                for e in self.entities
            ],
            "relations": [r.to_dict() for r in self.relations],
            "clauses": [
                {
                    "id": c.id,
                    "clause_type": c.clause_type.value,
                    "text_preview": c.text[:200],
                    "section_ref": c.section_ref,
                    "confidence": c.confidence,
                    "page_number": c.page_number,
                }
                for c in self.clauses
            ],
            "chunks": [c.to_dict() for c in self.chunks],
        }
