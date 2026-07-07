"""
Abstract interface and data classes for OCR engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from regulaforge.document_intelligence.domain.models import BoundingBox


@dataclass
class OcrWord:
    """A single word recognised by OCR."""

    text: str
    bbox: BoundingBox
    confidence: float = 0.0


@dataclass
class OcrPageResult:
    """OCR result for a single page."""

    page_number: int = 0
    text: str = ""
    words: list[OcrWord] = field(default_factory=list)
    confidence: float = 0.0
    language: str | None = None


@dataclass
class OcrResult:
    """Aggregated OCR results for a multi-page document."""

    pages: list[OcrPageResult] = field(default_factory=list)
    full_text: str = ""
    overall_confidence: float = 0.0

    @property
    def num_pages(self) -> int:
        return len(self.pages)


class OcrEngine(ABC):
    """Interface for OCR backends."""

    @abstractmethod
    async def recognize(self, image_path: Path, **kwargs: object) -> OcrPageResult:
        """Run OCR on a single page image.

        Args:
            image_path: Path to the page image.
            kwargs: Engine-specific options (language, psm, …).

        Returns:
            An ``OcrPageResult`` with recognised text and word-level details.
        """
        ...

    @abstractmethod
    async def recognize_multi(
        self, image_paths: list[Path], **kwargs: object
    ) -> OcrResult:
        """Run OCR on multiple page images.

        The default implementation calls ``recognize`` sequentially.
        Engines with batch support should override this method.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check whether the engine's binaries/libraries are installed."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name (e.g. ``"tesseract"``, ``"paddleocr"``)."""
        ...
