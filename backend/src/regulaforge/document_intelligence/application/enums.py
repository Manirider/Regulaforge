"""
Application-layer enums for the Document Intelligence platform.

Extends the domain enums with values used by the application and
infrastructure service layers (classification, relation extraction,
layout analysis, pipeline status).
"""

from __future__ import annotations

from enum import Enum


class ElementType(str, Enum):
    SECTION_HEADING = "section_heading"
    TITLE = "title"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE = "figure"
    LIST = "list"
    HEADER = "header"
    FOOTER = "footer"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    FORM = "form"
    PAGE_NUMBER = "page_number"
    OTHER = "other"


class ClassificationLabel(str, Enum):
    CIRCULAR = "circular"
    NOTIFICATION = "notification"
    MASTER_DIRECTION = "master_direction"
    GUIDELINE = "guideline"
    PRESS_RELEASE = "press_release"
    REPORT = "report"
    AMENDMENT = "amendment"
    LEGISLATION = "legislation"
    POLICY = "policy"
    STANDARD = "standard"
    CONTRACT = "contract"
    FORM = "form"
    OTHER = "other"


class RelationType(str, Enum):
    REFERENCES = "references"
    AMENDS = "amends"
    SUPERSEDES = "supersedes"
    REQUIRES = "requires"
    PENALIZES = "penalizes"
    DEFINES = "defines"
    RELATED_TO = "related_to"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    OCR_REQUIRED = "ocr_required"
    LAYOUT_ANALYSIS = "layout_analysis"
    NER_IN_PROGRESS = "ner_in_progress"
    CLASSIFYING = "classifying"
    CHUNKING = "chunking"
    COMPLETED = "completed"
    FAILED = "failed"
