from __future__ import annotations

import pytest
from regulaforge.document_intelligence.application.enums import ElementType
from regulaforge.document_intelligence.infrastructure.layout.layout_analyzer import LayoutAnalyzer
from regulaforge.document_intelligence.infrastructure.pdf.pdf_processor import PDFProcessor


class TestPDFProcessor:
    @pytest.fixture
    def processor(self) -> PDFProcessor:
        return PDFProcessor()

    @pytest.mark.asyncio
    async def test_extract_text_nonexistent_path(self, processor) -> None:
        with pytest.raises(FileNotFoundError):
            await processor.extract_text("/nonexistent/file.pdf")

    @pytest.mark.asyncio
    async def test_extract_text_raises_on_empty(self, processor) -> None:
        with pytest.raises(FileNotFoundError):
            await processor.extract_text("")


class TestLayoutAnalyzer:
    @pytest.fixture
    def analyzer(self) -> LayoutAnalyzer:
        return LayoutAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_empty(self, analyzer) -> None:
        result = await analyzer.analyze("", "")
        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_text(self, analyzer, sample_text) -> None:
        result = await analyzer.analyze("", sample_text)
        assert len(result) > 0
        types_found = {e.element_type for e in result}
        assert len(types_found) >= 2

    @pytest.mark.asyncio
    async def test_analyze_detects_section_heading(self, analyzer, sample_text) -> None:
        result = await analyzer.analyze("", sample_text)
        assert any(e.element_type == ElementType.SECTION_HEADING for e in result)

    @pytest.mark.asyncio
    async def test_analyze_detects_paragraph(self, analyzer, sample_text) -> None:
        result = await analyzer.analyze("", sample_text)
        assert any(e.element_type == ElementType.PARAGRAPH for e in result)

    @pytest.mark.asyncio
    async def test_analyze_detects_section_heading_upper(self, analyzer) -> None:
        text = "SECTION 3: KNOW YOUR CUSTOMER REQUIREMENTS"
        result = await analyzer.analyze("", text)
        assert any(e.element_type == ElementType.SECTION_HEADING for e in result)

    @pytest.mark.asyncio
    async def test_no_duplicates(self, analyzer, sample_text) -> None:
        result = await analyzer.analyze("", sample_text)
        keys = [(e.text[:100].lower(), e.page, e.element_type.value) for e in result]
        assert len(keys) == len(set(keys))
