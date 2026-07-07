from __future__ import annotations

import logging
from uuid import uuid4

from regulaforge.document_intelligence.application.models import (
    ConfidenceScore,
    ExtractedEntity,
)
from regulaforge.document_intelligence.domain.enums import EntityType

logger = logging.getLogger(__name__)


class TransformersNEREngine:
    def __init__(
        self,
        model_name: str = "dbmdz/bert-large-cased-finetuned-conll03-english",
        device: str = "cpu",
        max_length: int = 512,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._max_length = max_length
        self._pipeline = None

    async def load(self) -> None:
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "ner",
                model=self._model_name,
                device=self._device,
                aggregation_strategy="simple",
            )
            logger.info("NER model loaded: %s", self._model_name)
        except ImportError:
            logger.warning("Transformers not available for NER")
        except Exception as exc:
            logger.warning("Failed to load NER model: %s", exc)

    async def extract(self, text: str) -> list[ExtractedEntity]:
        if self._pipeline is None:
            await self.load()
        if self._pipeline is None:
            return []

        entities: list[ExtractedEntity] = []
        try:
            chunks = [text[i:i + self._max_length] for i in range(0, len(text), self._max_length - 100)]
            for chunk in chunks:
                results = self._pipeline(chunk)
                for r in results:
                    entity = ExtractedEntity(
                        id=uuid4(),
                        entity_type=self._map_label(r.get("entity_group", "MISC")),
                        text=r.get("word", ""),
                        start_char=r.get("start", 0),
                        end_char=r.get("end", 0),
                        page=0,
                        confidence=ConfidenceScore(
                            value=r.get("score", 0.5),
                            model=self._model_name,
                        ),
                    )
                    entities.append(entity)
        except Exception as exc:
            logger.warning("Transformer NER extraction failed: %s", exc)

        return entities

    def _map_label(self, label: str) -> EntityType:
        mapping = {
            "ORG": EntityType.ORGANIZATION,
            "PER": EntityType.PERSON,
            "LOC": EntityType.JURISDICTION,
            "MISC": EntityType.OTHER,
            "DATE": EntityType.DATE,
            "LAW": EntityType.REGULATION,
            "GPE": EntityType.JURISDICTION,
        }
        return mapping.get(label.upper(), EntityType.OTHER)
