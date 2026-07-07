"""
Abstract interface for document layout analysis engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from regulaforge.document_intelligence.domain.enums import ElementCategory
from regulaforge.document_intelligence.domain.models import BoundingBox, DocumentElement, PageLayout


@dataclass
class LayoutResult:
    """Full layout analysis result for a multi-page document."""

    pages: list[PageLayout] = field(default_factory=list)
    overall_confidence: float = 0.0
    num_pages: int = 0


class LayoutAnalyzer(ABC):
    """Interface for layout analysis backends."""

    @abstractmethod
    async def analyze_page(self, image_path: Path, page_number: int = 1, **kwargs: object) -> PageLayout:
        """Analyse the layout of a single page image.

        Args:
            image_path: Path to the rendered page image.
            page_number: 1-indexed page number.
            kwargs: Analyzer-specific options.

        Returns:
            A ``PageLayout`` with detected elements.
        """
        ...

    @abstractmethod
    async def analyze(self, image_paths: list[Path], **kwargs: object) -> LayoutResult:
        """Analyse layout across multiple pages."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check whether the analyzer's model/library is installed."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable analyzer name."""
        ...
