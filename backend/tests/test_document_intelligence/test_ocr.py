"""Tests for OCR engines."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from regulaforge.document_intelligence.domain.models import BoundingBox
from regulaforge.document_intelligence.ocr.base import OcrEngine, OcrPageResult, OcrResult, OcrWord


class AlwaysAvailableEngine(OcrEngine):
    @property
    def name(self) -> str:
        return "test-engine"

    async def is_available(self) -> bool:
        return True

    async def recognize(self, image_path: Path, **kwargs: object) -> OcrPageResult:
        return OcrPageResult(
            page_number=1,
            text="test text",
            words=[OcrWord(text="test", bbox=BoundingBox(0, 0, 10, 10), confidence=0.9)],
            confidence=0.9,
        )

    async def recognize_multi(self, image_paths: list[Path], **kwargs: object) -> OcrResult:
        pages = []
        for i, _ in enumerate(image_paths):
            pages.append(await self.recognize(_, page_number=i + 1))
        return OcrResult(
            pages=pages,
            full_text=" ".join(p.text for p in pages),
            overall_confidence=sum(p.confidence for p in pages) / len(pages),
        )


@pytest.mark.asyncio
async def test_ocr_engine_is_available():
    engine = AlwaysAvailableEngine()
    assert await engine.is_available()


@pytest.mark.asyncio
async def test_ocr_engine_recognize():
    engine = AlwaysAvailableEngine()
    result = await engine.recognize(Path("/fake/path.png"))
    assert isinstance(result, OcrPageResult)
    assert result.text == "test text"
    assert len(result.words) == 1


@pytest.mark.asyncio
async def test_ocr_engine_recognize_multi():
    engine = AlwaysAvailableEngine()
    result = await engine.recognize_multi([Path("/a.png"), Path("/b.png")])
    assert isinstance(result, OcrResult)
    assert len(result.pages) == 2
    assert result.full_text == "test text test text"
    assert result.overall_confidence == 0.9


def test_ocr_word_defaults():
    w = OcrWord(text="hello", bbox=BoundingBox(0, 0, 5, 5))
    assert w.confidence == 0.0


def test_ocr_page_result_defaults():
    r = OcrPageResult()
    assert r.text == ""
    assert r.words == []
    assert r.confidence == 0.0


def test_ocr_result_defaults():
    r = OcrResult()
    assert r.pages == []
    assert r.full_text == ""
    assert r.overall_confidence == 0.0


@pytest.mark.asyncio
async def test_tesseract_engine_not_available():
    from regulaforge.document_intelligence.ocr.tesseract_engine import TesseractEngine
    engine = TesseractEngine()
    available = await engine.is_available()
    # pytesseract may or may not be installed
    assert isinstance(available, bool)


@pytest.mark.asyncio
async def test_paddle_engine_not_available():
    from regulaforge.document_intelligence.ocr.paddle_engine import PaddleOcrEngine
    engine = PaddleOcrEngine()
    available = await engine.is_available()
    assert isinstance(available, bool)
