"""Text processing pipeline for regulatory documents.

Handles document parsing, chunking, tokenization, and
preprocessing for downstream AI tasks.
"""

import re

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


class TextProcessor:
    """Processes and prepares regulatory text for AI analysis.

    Provides chunking, cleaning, and structural analysis of
    regulatory documents to enable efficient AI processing.
    """

    # Section headers commonly found in regulations
    SECTION_PATTERNS = [  # noqa: RUF012
        re.compile(r"^(Article\s+\d+[\.\w]*)", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^(Section\s+\d+[\.\w]*)", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^(\d+\.\d+\s+[A-Z])", re.MULTILINE),
        re.compile(r"^([A-Z][A-Z\s]+)\s*$", re.MULTILINE),
    ]

    # Citation patterns (e.g., "Art. 5(1)(a)", "Section 404")
    CITATION_PATTERN = re.compile(
        r"(?:Art(?:icle)?\.?\s*(\d+(?:[\.\-\d]*))|"
        r"Sec(?:tion)?\.?\s*(\d+(?:[\.\-\d]*))|"
        r"Reg(?:ulation)?\.?\s*(\d+(?:[\.\-\d]*)))",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._chunk_size = settings.ai.max_chunk_size
        self._chunk_overlap = 200  # Character overlap between chunks

    def clean_text(self, text: str) -> str:
        """Clean and normalize regulatory text.

        Args:
            text: Raw document text.

        Returns:
            Cleaned and normalized text.
        """
        if not text:
            return ""

        # Normalize whitespace
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\s+", " ", text)

        # Normalize unicode
        text = text.replace("\u2013", "-").replace("\u2014", "--")
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')

        # Remove control characters except newlines
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

        return text.strip()

    def chunk_text(self, text: str) -> list[dict]:
        """Split text into overlapping chunks for AI processing.

        Uses semantic boundaries (sections, paragraphs) when possible.

        Args:
            text: The text to chunk.

        Returns:
            List of chunk dictionaries with 'text', 'index', and 'metadata'.
        """
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        chunks = []
        current_pos = 0
        chunk_index = 0

        while current_pos < len(cleaned):
            # Find chunk end
            end_pos = min(current_pos + self._chunk_size, len(cleaned))

            # Try to break at a natural boundary
            if end_pos < len(cleaned):
                # Look for paragraph break
                next_newline = cleaned.rfind("\n\n", current_pos, end_pos)
                if next_newline > current_pos + (self._chunk_size // 2):
                    end_pos = next_newline
                else:
                    # Look for sentence boundary
                    next_period = cleaned.rfind(". ", current_pos, end_pos)
                    if next_period > current_pos + (self._chunk_size // 2):
                        end_pos = next_period + 1

            chunk_text = cleaned[current_pos:end_pos].strip()
            if chunk_text:
                chunk_meta = self._extract_chunk_metadata(chunk_text, chunk_index)
                chunks.append({
                    "text": chunk_text,
                    "index": chunk_index,
                    "metadata": chunk_meta,
                })
                chunk_index += 1

            # Move position with overlap
            current_pos = end_pos - (self._chunk_overlap if end_pos < len(cleaned) else 0)

        logger.debug("Chunked text into %d chunks", len(chunks))
        return chunks

    def extract_sections(self, text: str) -> list[dict]:
        """Extract hierarchical sections from regulatory text.

        Args:
            text: Regulatory document text.

        Returns:
            List of section dictionaries with title, level, and content.
        """
        sections = []
        lines = text.split("\n")
        current_section = {"title": "Preamble", "level": 0, "content": []}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            matched = False
            for pattern in self.SECTION_PATTERNS:
                match = pattern.match(line)
                if match:
                    if current_section["content"]:
                        current_section["content"] = "\n".join(
                            current_section["content"]
                        )
                        sections.append(current_section)

                    level = 1 if "Article" in line or "Section" in line else 2
                    current_section = {
                        "title": line[:100],
                        "level": level,
                        "content": [],
                    }
                    matched = True
                    break

            if not matched:
                current_section["content"].append(line)

        # Add last section
        if current_section["content"]:
            current_section["content"] = "\n".join(current_section["content"])
            sections.append(current_section)

        return sections

    def extract_citations(self, text: str) -> list[str]:
        """Extract regulatory citations from text.

        Args:
            text: Text containing citations.

        Returns:
            List of extracted citation strings.
        """
        matches = self.CITATION_PATTERN.findall(text)
        citations = []
        for match in matches:
            for group in match:
                if group:
                    citations.append(group)
        return list(set(citations))

    def count_tokens(self, text: str) -> int:
        """Estimate token count for a text string.

        Uses a rough heuristic (~4 chars per token for English).

        Args:
            text: The text to estimate.

        Returns:
            Estimated token count.
        """
        return len(text) // 4

    def _extract_chunk_metadata(
        self, chunk_text: str, index: int
    ) -> dict:
        """Extract metadata from a text chunk."""
        sentences = re.split(r"[.!?]+", chunk_text)
        citations = self.extract_citations(chunk_text)

        return {
            "chunk_index": index,
            "sentence_count": len([s for s in sentences if s.strip()]),
            "char_count": len(chunk_text),
            "estimated_tokens": self.count_tokens(chunk_text),
            "citations": citations,
            "has_numbers": bool(re.search(r"\d+", chunk_text)),
        }
