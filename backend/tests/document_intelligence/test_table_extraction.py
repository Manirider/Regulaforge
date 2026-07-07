from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from regulaforge.document_intelligence.application.table_extraction import TableExtractionService
from regulaforge.document_intelligence.application.models import DocumentElement, TableCell
from regulaforge.document_intelligence.application.enums import ElementType


class TestTableExtractionService:
    @pytest.fixture
    def extractor(self) -> TableExtractionService:
        return TableExtractionService()

    @pytest.mark.asyncio
    async def test_extract_empty(self, extractor, tmp_path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        tables = await extractor.extract(str(f))
        assert tables == []

    @pytest.mark.asyncio
    async def test_extract_with_element_table(self, extractor, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("some text", encoding="utf-8")
        element = DocumentElement(
            id=uuid4(),
            element_type=ElementType.TABLE,
            text="Header1  Header2\nValue1   Value2",
            page=1,
        )
        tables = await extractor.extract(str(f), elements=[element])
        assert len(tables) >= 1
        t = tables[0]
        assert t.num_cols() >= 1

    @pytest.mark.asyncio
    async def test_extract_no_table_elements(self, extractor, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("text", encoding="utf-8")
        tables = await extractor.extract(str(f))
        assert tables == []
