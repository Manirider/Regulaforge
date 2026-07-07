"""
Application-layer models for the Document Intelligence platform.

These models serve the application services and infrastructure adapters,
providing richer processing-level types used during document analysis.
They are independent from the core domain models, which focus on
serializable output.

Every extraction result carries a ``ConfidenceScore`` object with
a numeric value, model provenance, and optional metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from regulaforge.document_intelligence.application.enums import (
    ClassificationLabel,
    ElementType,
    ProcessingStatus,
    RelationType,
)
from regulaforge.document_intelligence.domain.enums import DocumentType, EntityType


@dataclass
class ConfidenceScore:
    value: float = 1.0
    model: str = "rule"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.value = max(0.0, min(1.0, float(self.value)))

    @property
    def level(self) -> str:
        if self.value >= 0.9:
            return "very_high"
        if self.value >= 0.8:
            return "high"
        if self.value >= 0.7:
            return "medium"
        if self.value >= 0.5:
            return "low"
        return "very_low"



@dataclass
class BoundingBox:
    page: int = 0
    left: float = 0.0
    top: float = 0.0
    width: float = 0.0
    height: float = 0.0
    confidence: float = 1.0



@dataclass
class DocumentElement:
    id: str = ""
    element_type: ElementType = ElementType.OTHER
    text: str = ""
    page: int = 0
    bbox: BoundingBox | None = None
    confidence: ConfidenceScore | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[DocumentElement] = field(default_factory=list)



@dataclass
class TableCell:
    text: str = ""
    row: int = 0
    col: int = 0
    is_header: bool = False


@dataclass
class TableElement(DocumentElement):
    headers: list[str] = field(default_factory=list)
    rows: list[list[TableCell]] = field(default_factory=list)
    caption: str = ""

    def num_rows(self) -> int:
        return len(self.rows)

    def num_cols(self) -> int:
        if self.rows:
            return max(len(row) for row in self.rows)
        return len(self.headers)

    def to_markdown(self) -> str:
        if not self.headers and not self.rows:
            return ""
        lines = []
        if self.caption:
            lines.append(f"### {self.caption}")
            lines.append("")
        headers = self.headers or [f"Col {i+1}" for i in range(self.num_cols())]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in self.rows:
            row_text = [cell.text for cell in row]
            while len(row_text) < len(headers):
                row_text.append("")
            lines.append("| " + " | ".join(row_text[:len(headers)]) + " |")
        return "\n".join(lines)



@dataclass
class ExtractedEntity:
    id: str = ""
    entity_type: EntityType = EntityType.OTHER
    text: str = ""
    start_char: int = 0
    end_char: int = 0
    page: int = 0
    confidence: ConfidenceScore | None = None
    normalized_value: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticMetadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    published_date: str | None = None
    jurisdiction: str | None = None
    regulatory_body: str | None = None
    summary: str | None = None
    keywords: list[str] = field(default_factory=list)
    entities: list[ExtractedEntity] = field(default_factory=list)
    language: str | None = None
    page_count: int = 0
    word_count: int = 0
    char_count: int = 0
    confidence: ConfidenceScore | None = None
    is_scanned: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "published_date": self.published_date,
            "jurisdiction": self.jurisdiction,
            "regulatory_body": self.regulatory_body,
            "summary": self.summary,
            "keywords": self.keywords,
            "language": self.language,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "is_scanned": self.is_scanned,
        }


@dataclass
class ClassificationResult:
    label: ClassificationLabel = ClassificationLabel.OTHER
    confidence: ConfidenceScore | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextChunk:
    id: str = ""
    text: str = ""
    page: int = 0
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    section_title: str | None = None
    tokens: int = 0
    confidence: ConfidenceScore | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ListItem:
    text: str = ""
    level: int = 0
    ordinal: str = ""
    page: int = 0


@dataclass
class FormElement:
    id: str = ""
    page: int = 0
    confidence: ConfidenceScore | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    id: str = ""
    relation_type: RelationType = RelationType.RELATED_TO
    source_entity_id: str = ""
    target_entity_id: str = ""
    confidence: ConfidenceScore | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Clause:
    id: str = ""
    text: str = ""
    clause_id: str = ""
    page: int = 0
    bbox: BoundingBox | None = None
    confidence: ConfidenceScore | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    id: str = ""
    document_id: str = ""
    source_path: str = ""
    status: ProcessingStatus = ProcessingStatus.PENDING
    document_type: DocumentType = DocumentType.NATIVE_PDF
    raw_text: str = ""
    elements: list[DocumentElement] = field(default_factory=list)
    tables: list[TableElement] = field(default_factory=list)
    clauses: list[Clause] = field(default_factory=list)
    forms: list[FormElement] = field(default_factory=list)
    lists: list[ListItem] = field(default_factory=list)
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    classification: ClassificationResult | None = None
    chunks: list[TextChunk] = field(default_factory=list)
    metadata: SemanticMetadata | None = None
    error_message: str | None = None
    processing_time_ms: float = 0.0
    pipeline_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "source_path": self.source_path,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "document_type": self.document_type.value if hasattr(self.document_type, "value") else self.document_type,
            "elements": [e.to_dict() if hasattr(e, "to_dict") else e for e in self.elements],
            "tables": len(self.tables),
            "entities": len(self.entities),
            "relations": len(self.relations),
            "clauses": len(self.clauses),
            "chunks": len(self.chunks),
            "forms": len(self.forms),
            "lists": len(self.lists),
            "error": self.error_message,
            "processing_time_ms": self.processing_time_ms,
        }

    def merge(self, other: PipelineResult) -> None:
        """Merge another PipelineResult into this one."""
        self.elements.extend(other.elements)
        self.tables.extend(other.tables)
        self.clauses.extend(other.clauses)
        self.forms.extend(other.forms)
        self.lists.extend(other.lists)
        self.entities.extend(other.entities)
        self.relations.extend(other.relations)
        self.chunks.extend(other.chunks)
        if other.error_message and not self.error_message:
            self.error_message = other.error_message
        self.processing_time_ms += other.processing_time_ms



@dataclass
class FormField:
    label: str
    field_type: str = "text"
    value: Any = None
    confidence: float = 1.0

