"""
Enumerations for the Document Intelligence domain.
"""

from __future__ import annotations

from enum import Enum


class DocumentType(str, Enum):
    NATIVE_PDF = "native_pdf"
    SCANNED_PDF = "scanned_pdf"
    IMAGE = "image"
    DOCX = "docx"
    HTML = "html"
    TEXT = "text"


class ElementCategory(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    SUBHEADING = "subheading"
    TABLE = "table"
    LIST = "list"
    LIST_ITEM = "list_item"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    CAPTION = "caption"
    FIGURE = "figure"
    CHART = "chart"
    SIGNATURE = "signature"
    FORM_FIELD = "form_field"
    PAGE_NUMBER = "page_number"
    SIDEBAR = "sidebar"
    OTHER = "other"


class EntityType(str, Enum):
    ORGANIZATION = "organization"
    PERSON = "person"
    DATE = "date"
    AMOUNT = "amount"
    PERCENTAGE = "percentage"
    REGULATION_ID = "regulation_id"
    REGULATION = "regulation"
    SECTION_NUMBER = "section_number"
    SECTION = "section"
    LEGAL_TERM = "legal_term"
    TERM = "term"
    DEFINITION = "definition"
    CURRENCY = "currency"
    STATUTE = "statute"
    COURT_CASE = "court_case"
    ENTITY_NAME = "entity_name"
    ROLE = "role"
    ADDRESS = "address"
    CONTACT = "contact"
    JURISDICTION = "jurisdiction"
    PENALTY = "penalty"
    COMPLIANCE_ACTION = "compliance_action"
    CLAUSE_REF = "clause_ref"
    GUIDELINE = "guideline"
    OTHER = "other"


class ClauseType(str, Enum):
    DEFINITION = "definition"
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    PENALTY = "penalty"
    COMPLIANCE = "compliance"
    REPORTING = "reporting"
    EFFECTIVE_DATE = "effective_date"
    AMENDMENT = "amendment"
    REPEAL = "repeal"
    SAVINGS = "savings"
    JURISDICTION = "jurisdiction"
    TERMINATION = "termination"
    INDEMNITY = "indemnity"
    CONFIDENTIALITY = "confidentiality"
    GENERAL = "general"


class ProcessingStage(str, Enum):
    LOADED = "loaded"
    OCR_COMPLETE = "ocr_complete"
    LAYOUT_ANALYZED = "layout_analyzed"
    ENTITIES_EXTRACTED = "entities_extracted"
    RELATIONS_EXTRACTED = "relations_extracted"
    CLAUSES_IDENTIFIED = "clauses_identified"
    CHUNKED = "chunked"
    COMPLETE = "complete"
    FAILED = "failed"


class AnchorSide(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
