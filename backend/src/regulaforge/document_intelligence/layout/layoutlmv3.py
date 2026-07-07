"""
LayoutLMv3-based document layout analysis via HuggingFace Transformers.

Uses ``microsoft/layoutlmv3-base`` for image-level feature extraction.
Per-element layout classification requires a fine-tuned classification
head; this implementation provides the feature extraction backbone and
a configurable classifier interface.

The image processor and model are loaded on first use (lazy initialisation).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

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

MODEL_NAME = "microsoft/layoutlmv3-base"


def _default_element_classifier(
    _features: Any,
    _image_size: tuple[int, int],
) -> list[DocumentElement]:
    """Default element classifier: returns a single page-level element.

    Override by passing ``element_classifier`` to ``LayoutLmAnalyzer``.
    """
    return [
        DocumentElement(
            id="elem-1",
            category=ElementCategory.PARAGRAPH,
            bbox=BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0),
            text="",
            confidence=0.5,
        )
    ]


class LayoutLmAnalyzer(LayoutAnalyzer):
    """LayoutLMv3-based document layout analyzer.

    Args:
        model_name: HuggingFace model identifier.
        device: Torch device (``"cpu"`` or ``"cuda"``).
        batch_size: Images per inference batch.
        element_classifier: Optional callable that receives model features
            and returns a list of ``DocumentElement``.  Defaults to a
            single page-level element.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        device: str = "cpu",
        batch_size: int = 4,
        element_classifier: Callable[..., list[DocumentElement]] | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._element_classifier = element_classifier or _default_element_classifier
        self._processor = None
        self._model = None
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return "layoutlmv3"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _load(self) -> None:
        if self._processor is not None and self._model is not None:
            return
        from transformers import (
            LayoutLMv3ImageProcessor,
            LayoutLMv3Model,
        )

        self._processor = LayoutLMv3ImageProcessor.from_pretrained(
            self._model_name, apply_ocr=False,
        )
        self._model = LayoutLMv3Model.from_pretrained(
            self._model_name,
            device_map=self._device if self._device == "cpu" else None,
        )
        if self._device != "cpu" and self._model is not None:
            self._model.to(self._device)
        self._model.eval()

    async def analyze_page(
        self, image_path: Path, page_number: int = 1, **kwargs: Any
    ) -> PageLayout:
        self._load()
        from PIL import Image
        import torch

        image = Image.open(image_path).convert("RGB")
        width, height = image.size

        encoding = self._processor(images=image, return_tensors="pt")
        pixel_values = encoding["pixel_values"].to(self._device)

        with torch.no_grad():
            outputs = self._model(pixel_values=pixel_values)

        features = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs.last_hidden_state

        elements = self._element_classifier(features, (width, height))
        page_confidence = (
            sum(e.confidence for e in elements) / len(elements)
            if elements else 0.5
        )

        return PageLayout(
            page_number=page_number,
            width=float(width),
            height=float(height),
            elements=elements,
            confidence=page_confidence,
        )

    async def analyze(
        self, image_paths: list[Path], **kwargs: Any
    ) -> LayoutResult:
        pages: list[PageLayout] = []
        confidences: list[float] = []

        for i, path in enumerate(image_paths):
            page = await self.analyze_page(path, page_number=i + 1, **kwargs)
            pages.append(page)
            confidences.append(page.confidence)

        overall_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return LayoutResult(
            pages=pages,
            overall_confidence=overall_conf,
            num_pages=len(pages),
        )
