"""
Document metadata extraction (author, date, title, subject, source).
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from regulaforge.document_intelligence.domain.models import ExtractedEntity


@dataclass
class MetadataResult:
    title: str | None = None
    author: str | None = None
    creation_date: date | None = None
    modification_date: date | None = None
    subject: str | None = None
    source_url: str | None = None
    doc_id: str | None = None
    language: str | None = None
    page_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


class MetadataExtractor(ABC):
    @abstractmethod
    async def extract(
        self, file_path: Path, text: str | None = None, **kwargs: Any
    ) -> MetadataResult:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class PdfMetadataExtractor(MetadataExtractor):
    """PDF metadata extraction via PyMuPDF or pypdf fallback."""

    def __init__(self) -> None:
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return "pdf-metadata"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import fitz  # noqa: F401
            self._available = True
        except ImportError:
            try:
                import pypdf  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    async def extract(
        self, file_path: Path, text: str | None = None, **kwargs: Any
    ) -> MetadataResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._extract_sync, file_path,
        )

    def _extract_sync(self, file_path: Path) -> MetadataResult:
        """Synchronous metadata extraction (runs in thread executor)."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))
            try:
                meta = doc.metadata
                title = meta.get("title") or None
                author = meta.get("author") or None
                subject = meta.get("subject") or None

                creation_date = self._parse_pdf_date(meta.get("creationDate"))
                modification_date = self._parse_pdf_date(meta.get("modDate"))

                return MetadataResult(
                    title=title,
                    author=author,
                    creation_date=creation_date,
                    modification_date=modification_date,
                    subject=subject,
                    page_count=doc.page_count,
                    confidence=0.95,
                )
            finally:
                doc.close()
        except ImportError:
            pass

        try:
            import pypdf

            reader = pypdf.PdfReader(str(file_path))
            meta = reader.metadata
            return MetadataResult(
                title=meta.get("/Title") or None,
                author=meta.get("/Author") or None,
                subject=meta.get("/Subject") or None,
                creation_date=self._parse_pdf_date(
                    str(meta.get("/CreationDate", ""))
                ) if meta.get("/CreationDate") else None,
                modification_date=self._parse_pdf_date(
                    str(meta.get("/ModDate", ""))
                ) if meta.get("/ModDate") else None,
                page_count=len(reader.pages),
                confidence=0.90,
            )
        except ImportError:
            pass

        return MetadataResult(confidence=0.0)

    @staticmethod
    def _parse_pdf_date(date_str: str | None) -> date | None:
        if not date_str:
            return None
        match = re.search(r"(\d{4})(\d{2})(\d{2})", date_str)
        if match:
            from datetime import datetime
            return datetime.strptime(match.group(0), "%Y%m%d").date()
        return None


class TextMetadataExtractor(MetadataExtractor):
    """Extracts metadata from plain text using heuristics (first lines,
    common patterns)."""

    def __init__(self) -> None:
        self._available: bool = True

    @property
    def name(self) -> str:
        return "text-metadata"

    async def is_available(self) -> bool:
        return True

    async def extract(
        self, file_path: Path, text: str | None = None, **kwargs: Any
    ) -> MetadataResult:
        if not text:
            return MetadataResult()

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        title = None
        author = None
        creation_date = None

        title_patterns = [
            r"(?i)^(?:regulation|circular|notification|direction|order|guideline|act)\s+",
            r"(?i)^(?:report|policy|standard|code)\s+",
        ]

        if lines:
            first_line = lines[0]
            if any(re.match(p, first_line) for p in title_patterns):
                title = first_line[:200]
            elif len(first_line) > 10 and len(first_line) < 200:
                title = first_line

            for line in lines[1:6]:
                date_match = re.search(
                    r"(?i)(\d{1,2})\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})",
                    line,
                )
                if date_match:
                    from datetime import datetime
                    months = {
                        "january": 1, "february": 2, "march": 3, "april": 4,
                        "may": 5, "june": 6, "july": 7, "august": 8,
                        "september": 9, "october": 10, "november": 11, "december": 12,
                    }
                    try:
                        month = months[date_match.group(2).lower()]
                        day = int(date_match.group(1))
                        year = int(date_match.group(3))
                        creation_date = date(year, month, day)
                    except (ValueError, KeyError):
                        pass
                    break

                author_match = re.search(
                    r"(?i)(?:by\s+(?:the\s+)?(?:governor|chairman|secretary|director|board|authority))",
                    line,
                )
                if author_match:
                    author = line[:100]

        return MetadataResult(
            title=title,
            author=author,
            creation_date=creation_date,
            page_count=kwargs.get("page_count", 0),
            confidence=0.6,
        )
