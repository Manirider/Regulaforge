"""
HTML text and metadata extraction via BeautifulSoup4.

Strips script, style, nav, footer, and header tags before extracting
text.  Metadata is gathered from ``<meta>`` tags.
"""

from __future__ import annotations

from pathlib import Path

from regulaforge.ingestion.extractors.base import ExtractionResult, ExtractorBase, ExtractorError


class HtmlExtractor(ExtractorBase):
    def __init__(self) -> None:
        self._bs4_available = False
        try:
            import bs4  # noqa: F401
            self._bs4_available = True
        except ImportError:
            self._bs4_available = False

    def supports(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in (".html", ".htm") and filepath.exists()

    async def extract(self, filepath: Path, **kwargs: object) -> ExtractionResult:
        if not self.supports(filepath):
            return ExtractionResult(
                text="",
                success=False,
                error=f"Unsupported or missing file: {filepath}",
            )
        if not self._bs4_available:
            raise ExtractorError("HTML extraction requires beautifulsoup4")
        return await self._extract_with_bs4(filepath)

    async def _extract_with_bs4(self, filepath: Path) -> ExtractionResult:
        import bs4

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                html_content = f.read()

            soup = bs4.BeautifulSoup(html_content, "html.parser")

            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else None

            metadata: dict[str, object] = {}
            for meta in soup.find_all("meta"):
                name = meta.get("name") or meta.get("property")
                content = meta.get("content")
                if name and content:
                    metadata[str(name)] = str(content)

            return ExtractionResult(
                text=text,
                title=title,
                author=metadata.get("author"),
                publication_date=(
                    metadata.get("date")
                    or metadata.get("article:published_time")
                    or metadata.get("publication-date")
                ),
                metadata=metadata,
            )
        except Exception as e:
            raise ExtractorError(f"HTML extraction failed: {e}") from e
