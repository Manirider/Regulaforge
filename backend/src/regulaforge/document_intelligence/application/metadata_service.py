from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from regulaforge.document_intelligence.application.models import (
    ClassificationResult,
    ConfidenceScore,
    DocumentElement,
    ExtractedEntity,
    SemanticMetadata,
    TableElement,
)

logger = logging.getLogger(__name__)


class MetadataService:
    async def generate(
        self,
        text: str,
        elements: Optional[list[DocumentElement]] = None,
        entities: Optional[list[ExtractedEntity]] = None,
        tables: Optional[list[TableElement]] = None,
        classification: Optional[ClassificationResult] = None,
        source_path: str = "",
    ) -> SemanticMetadata:
        lines = [line for line in text.split("\n") if line.strip()]
        word_count = len(text.split())
        char_count = len(text)

        title = self._extract_title(text, Path(source_path).stem if source_path else None)
        pdf_meta = await self._extract_pdf_metadata(source_path)

        authors = pdf_meta.get("authors", [])
        published_date = pdf_meta.get("created")
        page_count = pdf_meta.get("page_count", 0)
        language = pdf_meta.get("language")

        keywords = self._extract_keywords(text, classification)
        summary = self._generate_summary(text)

        return SemanticMetadata(
            title=title,
            authors=authors,
            published_date=published_date,
            jurisdiction=self._extract_jurisdiction(text, entities),
            regulatory_body=self._extract_regulatory_body(text, entities),
            summary=summary,
            keywords=keywords,
            entities=entities or [],
            language=language,
            page_count=page_count,
            word_count=word_count,
            char_count=char_count,
            confidence=ConfidenceScore(
                value=0.85 if title else 0.5,
                model="metadata_pipeline",
                metadata={"has_title": title is not None, "has_pdf_meta": bool(pdf_meta)},
            ),
        )

    def _extract_title(self, text: str, fallback: Optional[str] = None) -> Optional[str]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return fallback

        for line in lines[:10]:
            if re.match(r"^(?:CIRCULAR|NOTIFICATION|MASTER DIRECTION|GUIDELINES|PRESS RELEASE|REPORT|AMENDMENT)\b", line, re.IGNORECASE):  # noqa: E501
                return line[:500]

        for i, line in enumerate(lines[:5]):
            if len(line) > 20 and len(line) < 200 and line.isupper():
                return line[:500]
            if len(line) > 30 and line[0].isupper() and i == 0:
                return line[:500]

        return fallback[:500] if fallback else None

    async def _extract_pdf_metadata(self, path: str) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        if not path.lower().endswith(".pdf"):
            return meta
        try:
            import fitz
            doc = fitz.open(path)
            meta = {
                "page_count": len(doc),
                "title": doc.metadata.get("title"),
                "authors": [a.strip() for a in doc.metadata.get("author", "").split(",") if a.strip()],
                "language": doc.metadata.get("language"),
            }
            created = doc.metadata.get("creationDate")
            if created:
                from datetime import datetime
                try:
                    fitz.get_pdf_now()  # fallback
                    meta["created"] = datetime.now()
                except Exception:
                    pass
            doc.close()
        except ImportError:
            logger.debug("PyMuPDF not available for metadata extraction")
        except Exception as exc:
            logger.warning("PDF metadata extraction failed: %s", exc)
        return meta

    def _extract_keywords(self, text: str, classification: Optional[ClassificationResult] = None) -> list[str]:
        import collections
        words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        stop_words = {"The", "This", "That", "These", "Those", "Such", "Which", "Where", "When", "What", "With", "From", "Into", "Upon", "After", "Before", "During", "Within", "Without", "Under", "Over", "Above", "Below", "Between", "Among"}  # noqa: E501
        filtered = [w for w in words if w not in stop_words and len(w) > 3]
        counter = collections.Counter(filtered)
        keywords = [w for w, _ in counter.most_common(15)]

        if classification:
            keywords.insert(0, classification.label.value.replace("_", " ").title())

        return keywords[:20]

    def _generate_summary(self, text: str, max_sentences: int = 3) -> Optional[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        meaningful = [s.strip() for s in sentences if len(s.strip()) > 30]
        if not meaningful:
            return None
        return " ".join(meaningful[:max_sentences])[:1000]

    def _extract_jurisdiction(self, text: str, entities: Optional[list[ExtractedEntity]] = None) -> Optional[str]:
        if entities:
            for e in entities:
                if e.entity_type.value == "jurisdiction":
                    return e.text
        jurisdictions = re.findall(r"(India|United States|European Union|United Kingdom|Singapore|UAE|APAC|EU|UK|US)", text)  # noqa: E501
        return jurisdictions[0] if jurisdictions else None

    def _extract_regulatory_body(self, text: str, entities: Optional[list[ExtractedEntity]] = None) -> Optional[str]:
        if entities:
            for e in entities:
                if e.entity_type.value == "organization" and ("Bank" in e.text or "Board" in e.text or "Authority" in e.text):  # noqa: E501
                    return e.text
        bodies = re.findall(r"(Reserve Bank of India|Securities and Exchange Board of India|Insurance Regulatory and Development Authority|Ministry of [A-Z][A-Za-z\s]+)", text)  # noqa: E501
        return bodies[0] if bodies else None
