from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import uuid4

from regulaforge.document_intelligence.application.models import (
    ConfidenceScore,
    DocumentElement,
    ExtractedEntity,
)
from regulaforge.document_intelligence.domain.enums import EntityType
from regulaforge.document_intelligence.infrastructure.ner.transformers_ner import TransformersNEREngine

logger = logging.getLogger(__name__)


class NERService:
    REGULATORY_PATTERNS: dict[EntityType, list[str]] = {  # noqa: RUF012
        EntityType.REGULATION: [
            r"(Regulation\s+\(?(?:EU|EC|EEC)?\s*No\s*\d+/\d+)",
            r"(The\s+(?:Securities|Banking|Insurance|Companies|Finance)\s+Act\s*\d*)",
            r"(Master\s+Direction\s+(?:on\s+)?[A-Z][A-Za-z\s]+)",
        ],
        EntityType.SECTION: [
            r"(Section\s+\d+[A-Za-z]?(?:\([^)]+\))?)",
            r"(Article\s+\d+[A-Za-z]?(?:\([^)]+\))?)",
            r"(Clause\s+\d+[.\d]*)",
            r"(Schedule\s+[IVXLCDM]+|\d+)",
        ],
        EntityType.DATE: [
            r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{2}/\d{2}/\d{4})",
        ],
        EntityType.AMOUNT: [
            r"(Rs\.?\s*[\d,]+(?:\.\d{2})?(?:\s*(?:crore|lakh|thousand|billion|million))?)",
            r"(INR\s*[\d,]+(?:\.\d{2})?)",
            r"([\d,]+(?:\.\d{2})?\s*(?:crore|lakh|thousand|billion|million))",
        ],
        EntityType.PERCENTAGE: [
            r"(\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*percent)",
        ],
        EntityType.ORGANIZATION: [
            r"(Reserve Bank of India)",
            r"(Securities and Exchange Board of India)",
            r"(Insurance Regulatory and Development Authority)",
            r"(Ministry of (?:Finance|Corporate Affairs|Law|Commerce))",
        ],
        EntityType.JURISDICTION: [
            r"(India|United States|European Union|United Kingdom|Singapore|UAE)",
        ],
        EntityType.PENALTY: [
            r"(penalty\s+(?:of\s+)?(?:Rs\.?|INR)?\s*[\d,]+)",
            r"(fine\s+(?:of\s+)?(?:Rs\.?|INR)?\s*[\d,]+)",
            r"(imprisonment\s+(?:for\s+)?(?:a\s+)?term\s+(?:of\s+)?[\d\s]+(?:years?|months?))",
        ],
        EntityType.COMPLIANCE_ACTION: [
            r"(shall\s+(?:comply|ensure|maintain|submit|file|obtain|disclose|report))",
            r"(must\s+(?:comply|ensure|maintain|submit|file|obtain|disclose|report))",
            r"(required\s+to\s+(?:comply|ensure|maintain|submit|file|obtain|disclose|report))",
        ],
    }

    def __init__(
        self,
        transformer_engine: Optional[TransformersNEREngine] = None,
        use_transformers: bool = False,
    ) -> None:
        self._transformer = transformer_engine
        self._use_transformers = use_transformers and transformer_engine is not None

    async def extract(
        self,
        text: str,
        elements: Optional[list[DocumentElement]] = None,
    ) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        seen: set[tuple[str, str]] = set()

        for entity_type, patterns in self.REGULATORY_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group(1) if match.lastindex else match.group(0)
                    start, end = match.start(1) if match.lastindex else match.start(), match.end(1) if match.lastindex else match.end()  # noqa: E501
                    dedup_key = (matched_text.lower().strip(), entity_type.value)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    entity = ExtractedEntity(
                        id=uuid4(),
                        entity_type=entity_type,
                        text=matched_text.strip()[:500],
                        start_char=start,
                        end_char=end,
                        page=self._find_page(start, elements) if elements else 0,
                        confidence=ConfidenceScore(value=0.85, model="regex"),
                        normalized_value=self._normalize(entity_type, matched_text.strip()),
                    )
                    entities.append(entity)

        if self._use_transformers and self._transformer:
            try:
                transformer_entities = await self._transformer.extract(text)
                for te in transformer_entities:
                    dedup_key = (te.text.lower().strip(), te.entity_type.value)
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        entities.append(te)
            except Exception as exc:
                logger.warning("Transformer NER failed, using regex results only: %s", exc)

        entities.sort(key=lambda e: e.start_char)
        logger.info("NER extracted %d entities from %d patterns", len(entities), len(self.REGULATORY_PATTERNS))
        return entities

    def _find_page(self, _char_pos: int, elements: list[DocumentElement]) -> int:
        for _elem in elements:
            pass
        return 1

    def _normalize(self, entity_type: EntityType, text: str) -> Optional[str]:
        if entity_type == EntityType.AMOUNT:
            nums = re.findall(r"[\d,]+(?:\.\d{2})?", text)
            return nums[0].replace(",", "") if nums else None
        if entity_type == EntityType.PERCENTAGE:
            nums = re.findall(r"\d+(?:\.\d+)?", text)
            return nums[0] if nums else None
        if entity_type == EntityType.DATE:
            months = {
                "January": "01", "February": "02", "March": "03", "April": "04",
                "May": "05", "June": "06", "July": "07", "August": "08",
                "September": "09", "October": "10", "November": "11", "December": "12",
            }
            for name, num in months.items():
                if name in text:
                    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+" + name + r"\s+(\d{4})", text)
                    if m:
                        return f"{m.group(2)}-{num}-{int(m.group(1)):02d}"
                    break
            return None
        return None
