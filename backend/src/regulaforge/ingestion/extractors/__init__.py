"""
Content extraction adapters for PDF and HTML documents.

Extractors implement the ``ExtractorBase`` interface and are selected
by the pipeline based on file extension.  Each extractor handles its
own import-graceful degradation (e.g. PyMuPDF → pypdf fallback).
"""

from regulaforge.ingestion.extractors.base import (
    ExtractionResult,
    ExtractorBase,
    ExtractorError,
)
from regulaforge.ingestion.extractors.pdf import PdfExtractor
from regulaforge.ingestion.extractors.html import HtmlExtractor

__all__ = [
    "ExtractionResult",
    "ExtractorBase",
    "ExtractorError",
    "PdfExtractor",
    "HtmlExtractor",
]
