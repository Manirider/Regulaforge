"""
PDF text and metadata extraction via PyMuPDF (fast path) or pypdf (fallback).

Gracefully degrades if neither library is installed and raises
``ExtractorError`` only when both are unavailable.
"""

from __future__ import annotations

from pathlib import Path

from regulaforge.ingestion.extractors.base import ExtractionResult, ExtractorBase, ExtractorError


class PdfExtractor(ExtractorBase):
    def __init__(self) -> None:
        self._pypdf_available = False
        self._pymupdf_available = False
        self._import_libraries()

    def _import_libraries(self) -> None:
        try:
            import pypdf  # noqa: F401
            self._pypdf_available = True
        except ImportError:
            self._pypdf_available = False
        try:
            import fitz  # noqa: F401
            self._pymupdf_available = True
        except ImportError:
            self._pymupdf_available = False

    def supports(self, filepath: Path) -> bool:
        return filepath.suffix.lower() == ".pdf" and filepath.exists()

    async def extract(self, filepath: Path, **kwargs: object) -> ExtractionResult:
        if not self.supports(filepath):
            return ExtractionResult(
                text="",
                success=False,
                error=f"Unsupported or missing file: {filepath}",
            )

        if self._pymupdf_available:
            return await self._extract_with_pymupdf(filepath)
        if self._pypdf_available:
            return await self._extract_with_pypdf(filepath)
        raise ExtractorError("No PDF library available (install pypdf or PyMuPDF)")

    async def _extract_with_pypdf(self, filepath: Path) -> ExtractionResult:
        import pypdf

        try:
            reader = pypdf.PdfReader(str(filepath))
            text_parts: list[str] = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            text = "\n".join(text_parts)

            metadata: dict[str, object] = {}
            if reader.metadata:
                for key in dir(reader.metadata):
                    val = getattr(reader.metadata, key)
                    if val is not None and not key.startswith("_"):
                        metadata[str(key)] = str(val)

            return ExtractionResult(
                text=text,
                title=metadata.get("/Title"),
                author=metadata.get("/Author"),
                page_count=len(reader.pages),
                metadata=metadata,
            )
        except Exception as e:
            raise ExtractorError(f"pypdf extraction failed: {e}") from e

    async def _extract_with_pymupdf(self, filepath: Path) -> ExtractionResult:
        import fitz

        try:
            doc = fitz.open(str(filepath))
            text_parts: list[str] = []
            for page in doc:
                text_parts.append(page.get_text())
            text = "\n".join(text_parts)

            metadata: dict[str, object] = {}
            for key, val in doc.metadata.items():
                if val:
                    metadata[str(key)] = str(val)

            page_count = len(doc)
            doc.close()

            return ExtractionResult(
                text=text,
                title=metadata.get("title"),
                author=metadata.get("author"),
                page_count=page_count,
                metadata=metadata,
            )
        except Exception as e:
            raise ExtractorError(f"PyMuPDF extraction failed: {e}") from e
