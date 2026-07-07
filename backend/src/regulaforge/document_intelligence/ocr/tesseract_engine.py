"""
Tesseract OCR engine integration.

Requires ``pytesseract`` and a system installation of Tesseract 5.x.
Gracefully handles missing dependencies via ``is_available()``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from regulaforge.document_intelligence.domain.models import BoundingBox
from regulaforge.document_intelligence.ocr.base import (
    OcrEngine,
    OcrPageResult,
    OcrResult,
    OcrWord,
)

DEFAULT_LANGUAGE = "eng"
DEFAULT_PSM = 3  # Fully automatic page segmentation

class TesseractEngine(OcrEngine):
    """OCR engine backed by Tesseract 5.x via ``pytesseract``.

    Args:
        language: Tesseract language code (default ``"eng"``).
        psm: Page segmentation mode (default 3 = fully automatic).
        timeout: Per-page OCR timeout in seconds.
    """

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        psm: int = DEFAULT_PSM,
        timeout: int = 120,
    ) -> None:
        self._language = language
        self._psm = psm
        self._timeout = timeout
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return "tesseract"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        if shutil.which("tesseract") is None:
            self._available = False
            return False
        try:
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            self._available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._available = False
        return self._available

    async def recognize(self, image_path: Path, **kwargs: object) -> OcrPageResult:
        import pytesseract

        lang = kwargs.get("language", self._language)
        psm = kwargs.get("psm", self._psm)
        config = f"--psm {psm} --oem 3"

        data = pytesseract.image_to_data(
            str(image_path),
            lang=lang,
            config=config,
            output_type=pytesseract.Output.DICT,
            timeout=self._timeout,
        )

        words: list[OcrWord] = []
        text_parts: list[str] = []
        confidences: list[float] = []

        n = len(data.get("text", []))
        for i in range(n):
            word_text = data["text"][i].strip()
            conf = int(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.0
            if not word_text:
                continue
            w = float(data["width"][i])
            h_val = float(data["height"][i])
            if w <= 0 or h_val <= 0:
                continue
            bbox = BoundingBox(
                x0=data["left"][i],
                y0=data["top"][i],
                x1=data["left"][i] + w,
                y1=data["top"][i] + h_val,
            )
            words.append(OcrWord(text=word_text, bbox=bbox, confidence=conf))
            text_parts.append(word_text)
            confidences.append(conf)

        page_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return OcrPageResult(
            page_number=kwargs.get("page_number", 0),
            text=" ".join(text_parts),
            words=words,
            confidence=page_conf,
            language=lang,
        )

    async def recognize_multi(
        self, image_paths: list[Path], **kwargs: object
    ) -> OcrResult:
        pages: list[OcrPageResult] = []
        full_text_parts: list[str] = []
        confidences: list[float] = []

        for i, path in enumerate(image_paths):
            kwargs["page_number"] = i + 1
            page_result = await self.recognize(path, **kwargs)
            pages.append(page_result)
            full_text_parts.append(page_result.text)
            confidences.append(page_result.confidence)

        overall_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(
            pages=pages,
            full_text="\n\n".join(full_text_parts),
            overall_confidence=overall_conf,
        )
