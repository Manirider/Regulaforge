from __future__ import annotations

import pytest
from regulaforge.document_intelligence.application.ocr_service import OCRService
from regulaforge.document_intelligence.application.models import ConfidenceScore


class TestOCRService:
    @pytest.fixture
    def ocr_service(self) -> OCRService:
        return OCRService()

    @pytest.mark.asyncio
    async def test_process_empty_list(self, ocr_service) -> None:
        result = await ocr_service.process([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_process_single_fake_path(self, ocr_service) -> None:
        result = await ocr_service.process(["/nonexistent.png"])
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_process_single(self, ocr_service) -> None:
        text, conf = await ocr_service.process_single("/nonexistent.png")
        assert isinstance(text, str)
        assert isinstance(conf, ConfidenceScore)

    @pytest.mark.asyncio
    async def test_process_single_fallback_confidence(self, ocr_service) -> None:
        _, conf = await ocr_service.process_single("/nonexistent.png")
        assert 0.0 <= conf.value <= 1.0
