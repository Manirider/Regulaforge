"""
PaddleOCR engine integration.

Requires ``paddleocr`` and the PaddleOCR model weights.  Gracefully
handles missing dependencies via ``is_available()``.
"""

from __future__ import annotations

from pathlib import Path

from regulaforge.document_intelligence.domain.models import BoundingBox
from regulaforge.document_intelligence.ocr.base import (
    OcrEngine,
    OcrPageResult,
    OcrResult,
    OcrWord,
)


class PaddleOcrEngine(OcrEngine):
    """OCR engine backed by PaddleOCR.

    Args:
        language: Language code (default ``"en"``).
        use_angle_cls: Whether to use the text direction classifier.
        gpu: Whether to use GPU inference.
    """

    def __init__(
        self,
        language: str = "en",
        use_angle_cls: bool = True,
        gpu: bool = False,
    ) -> None:
        self._language = language
        self._use_angle_cls = use_angle_cls
        self._gpu = gpu
        self._ocr = None
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return "paddleocr"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import paddleocr  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                use_angle_cls=self._use_angle_cls,
                lang=self._language,
                use_gpu=self._gpu,
                show_log=False,
            )
        return self._ocr

    async def recognize(self, image_path: Path, **kwargs: object) -> OcrPageResult:
        ocr = self._get_ocr()
        result = ocr.ocr(str(image_path), cls=self._use_angle_cls)

        words: list[OcrWord] = []
        text_parts: list[str] = []
        confidences: list[float] = []

        if result and result[0]:
            for line in result[0]:
                bbox_coords = line[0]
                text, conf = line[1]

                xs = [p[0] for p in bbox_coords]
                ys = [p[1] for p in bbox_coords]
                bbox = BoundingBox(
                    x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys),
                )

                words.append(
                    OcrWord(text=text, bbox=bbox, confidence=conf)
                )
                text_parts.append(text)
                confidences.append(conf)

        page_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrPageResult(
            page_number=kwargs.get("page_number", 0),
            text=" ".join(text_parts),
            words=words,
            confidence=page_conf,
            language=self._language,
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
