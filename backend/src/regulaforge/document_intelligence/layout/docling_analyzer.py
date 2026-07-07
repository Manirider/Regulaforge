"""
Docling-based document layout analysis.

Uses IBM's Docling library for PDF-to-structured-document conversion
with full layout preservation (tables, lists, headings, etc.).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from regulaforge.document_intelligence.domain.enums import ElementCategory
from regulaforge.document_intelligence.domain.models import (
    BoundingBox,
    DocumentElement,
    PageLayout,
)
from regulaforge.document_intelligence.layout.base import (
    LayoutAnalyzer,
    LayoutResult,
)


class DoclingAnalyzer(LayoutAnalyzer):
    """Document layout analyzer powered by IBM Docling.

    Args:
        use_gpu: Whether to enable GPU acceleration.
        timeout: Document conversion timeout in seconds.
    """

    def __init__(self, use_gpu: bool = False, timeout: int = 300) -> None:
        self._use_gpu = use_gpu
        self._timeout = timeout
        self._doc_converter = None
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return "docling"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import docling  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _get_converter(self):
        if self._doc_converter is None:
            from docling.document_converter import DocumentConverter

            self._doc_converter = DocumentConverter()
        return self._doc_converter

    async def analyze_page(self, image_path: Path, page_number: int = 1, **kwargs: object) -> PageLayout:
        raise NotImplementedError(
            "DoclingAnalyzer operates on full PDFs, not per-page. Use analyze() instead."
        )

    async def analyze(self, image_paths: list[Path], **kwargs: object) -> LayoutResult:
        if not image_paths:
            return LayoutResult()

        pdf_path = image_paths[0]
        if not pdf_path.suffix.lower() == ".pdf":
            return LayoutResult()

        converter = self._get_converter()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, converter.convert, str(pdf_path),
        )

        docling_doc = result.document
        pages: list[PageLayout] = []
        confidences: list[float] = []

        for page_num, page_item in docling_doc.pages.items():
            page = page_item
            elements: list[DocumentElement] = []

            for idx, item in enumerate(page.items):
                category = self._map_label(item.label)
                bbox = BoundingBox(
                    x0=item.bbox.l, y0=item.bbox.t, x1=item.bbox.r, y1=item.bbox.b,
                )
                text = item.text if hasattr(item, "text") else ""
                elements.append(
                    DocumentElement(
                        id=f"elem-{idx + 1}",
                        category=category,
                        bbox=bbox,
                        text=text,
                        confidence=0.95,
                    )
                )

            page_width = float(page.size.width) if page.size else 0.0
            page_height = float(page.size.height) if page.size else 0.0

            pages.append(
                PageLayout(
                    page_number=page_num,
                    width=page_width,
                    height=page_height,
                    elements=elements,
                    confidence=0.95,
                )
            )
            confidences.append(0.95)

        overall_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return LayoutResult(
            pages=pages,
            overall_confidence=overall_conf,
            num_pages=len(pages),
        )

    @staticmethod
    def _map_label(label: str) -> ElementCategory:
        mapping = {
            "heading": ElementCategory.HEADING,
            "subheading-level-1": ElementCategory.SUBHEADING,
            "subheading-level-2": ElementCategory.SUBHEADING,
            "paragraph": ElementCategory.PARAGRAPH,
            "table": ElementCategory.TABLE,
            "list": ElementCategory.LIST,
            "list-item": ElementCategory.LIST_ITEM,
            "header": ElementCategory.HEADER,
            "footer": ElementCategory.FOOTER,
            "figure": ElementCategory.FIGURE,
            "caption": ElementCategory.CAPTION,
            "formula": ElementCategory.OTHER,
            "checkbox-on": ElementCategory.FORM_FIELD,
            "checkbox-off": ElementCategory.FORM_FIELD,
            "code": ElementCategory.OTHER,
            "reference": ElementCategory.FOOTNOTE,
        }
        return mapping.get(label, ElementCategory.OTHER)
