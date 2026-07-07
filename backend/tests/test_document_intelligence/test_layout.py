"""Tests for layout analysis engines."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulaforge.document_intelligence.domain.enums import ElementCategory
from regulaforge.document_intelligence.domain.models import BoundingBox, DocumentElement, PageLayout
from regulaforge.document_intelligence.layout.base import LayoutAnalyzer, LayoutResult


class AlwaysAvailableAnalyzer(LayoutAnalyzer):
    @property
    def name(self) -> str:
        return "test-analyzer"

    async def is_available(self) -> bool:
        return True

    async def analyze_page(self, image_path: Path, page_number: int = 1, **kwargs: object) -> PageLayout:
        return PageLayout(
            page_number=page_number,
            width=612,
            height=792,
            elements=[
                DocumentElement(
                    id="elem-1",
                    category=ElementCategory.PARAGRAPH,
                    bbox=BoundingBox(10, 10, 100, 50),
                    confidence=0.95,
                ),
            ],
            confidence=0.95,
        )

    async def analyze(self, image_paths: list[Path], **kwargs: object) -> LayoutResult:
        pages = []
        confidences = []
        for i, _ in enumerate(image_paths):
            page = await self.analyze_page(_, page_number=i + 1)
            pages.append(page)
            confidences.append(page.confidence)
        return LayoutResult(
            pages=pages,
            overall_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
            num_pages=len(pages),
        )


@pytest.mark.asyncio
async def test_analyzer_available():
    a = AlwaysAvailableAnalyzer()
    assert await a.is_available()


@pytest.mark.asyncio
async def test_analyzer_analyze_page():
    a = AlwaysAvailableAnalyzer()
    result = await a.analyze_page(Path("/fake.png"))
    assert result.page_number == 1
    assert len(result.elements) == 1
    assert result.elements[0].category == ElementCategory.PARAGRAPH


@pytest.mark.asyncio
async def test_analyzer_analyze_multi():
    a = AlwaysAvailableAnalyzer()
    result = await a.analyze([Path("/a.png"), Path("/b.png")])
    assert result.num_pages == 2
    assert result.overall_confidence == 0.95


def test_document_element_defaults():
    el = DocumentElement(id="test", category=ElementCategory.TABLE, bbox=BoundingBox(0, 0, 10, 10))
    assert el.text == ""
    assert el.confidence == 1.0


def test_layout_result_empty():
    r = LayoutResult()
    assert r.pages == []
    assert r.num_pages == 0


@pytest.mark.asyncio
async def test_layoutlmv3_not_available():
    from regulaforge.document_intelligence.layout.layoutlmv3 import LayoutLmAnalyzer
    a = LayoutLmAnalyzer()
    assert not await a.is_available()


@pytest.mark.asyncio
async def test_docling_not_available():
    from regulaforge.document_intelligence.layout.docling_analyzer import DoclingAnalyzer
    a = DoclingAnalyzer()
    assert not await a.is_available()


@pytest.mark.asyncio
async def test_docling_analyze_empty():
    from regulaforge.document_intelligence.layout.docling_analyzer import DoclingAnalyzer
    a = DoclingAnalyzer()
    result = await a.analyze([])
    assert result.num_pages == 0


@pytest.mark.asyncio
async def test_docling_analyze_non_pdf():
    from regulaforge.document_intelligence.layout.docling_analyzer import DoclingAnalyzer
    a = DoclingAnalyzer()
    result = await a.analyze([Path("/fake.png")])
    assert result.num_pages == 0


def test_docling_label_mapping():
    from regulaforge.document_intelligence.layout.docling_analyzer import DoclingAnalyzer
    assert DoclingAnalyzer._map_label("heading") == ElementCategory.HEADING
    assert DoclingAnalyzer._map_label("paragraph") == ElementCategory.PARAGRAPH
    assert DoclingAnalyzer._map_label("table") == ElementCategory.TABLE
    assert DoclingAnalyzer._map_label("header") == ElementCategory.HEADER
    assert DoclingAnalyzer._map_label("footer") == ElementCategory.FOOTER
    assert DoclingAnalyzer._map_label("figure") == ElementCategory.FIGURE
    assert DoclingAnalyzer._map_label("list") == ElementCategory.LIST
    assert DoclingAnalyzer._map_label("reference") == ElementCategory.FOOTNOTE
    assert DoclingAnalyzer._map_label("unknown") == ElementCategory.OTHER
