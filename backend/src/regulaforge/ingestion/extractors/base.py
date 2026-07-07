from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractionResult:
    text: str
    title: str | None = None
    author: str | None = None
    publication_date: str | None = None
    page_count: int | None = None
    language: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    success: bool = True
    error: str | None = None


class ExtractorError(Exception):
    pass


class ExtractorBase(ABC):
    @abstractmethod
    async def extract(self, filepath: Path, **kwargs: object) -> ExtractionResult:
        ...

    @abstractmethod
    def supports(self, filepath: Path) -> bool:
        ...
