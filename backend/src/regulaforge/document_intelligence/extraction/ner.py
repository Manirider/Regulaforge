"""
Named Entity Recognition engine.

Supports spaCy (fast, production-ready) and HuggingFace transformers
for financial-domain NER.  Lazy-loads models on first use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from regulaforge.document_intelligence.domain.enums import EntityType
from regulaforge.document_intelligence.domain.models import ExtractedEntity

FINANCIAL_ENTITY_KEYWORDS: dict[EntityType, list[str]] = {
    EntityType.REGULATION_ID: [
        "regulation", "circular", "directive", "notification", "guideline",
        "master direction", "order", "act", "rule", "schedule",
    ],
    EntityType.SECTION_NUMBER: [
        "section", "subsection", "paragraph", "clause", "annex", "schedule",
    ],
    EntityType.AMOUNT: [
        "rupees", "lakh", "crore", "million", "billion", "trillion",
        "rs", "₹", "$", "€", "£",
    ],
}


@dataclass
class NerResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    overall_confidence: float = 0.0


class NerEngine(ABC):
    @abstractmethod
    async def extract(self, text: str, **kwargs: Any) -> NerResult:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class SpacyNerEngine(NerEngine):
    """NER engine powered by spaCy.

    Args:
        model_name: spaCy model name (default ``"en_core_web_trf"``).
    """

    def __init__(self, model_name: str = "en_core_web_trf") -> None:
        self._model_name = model_name
        self._nlp = None
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return f"spacy:{self._model_name}"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import spacy  # noqa: F401
            import spacy.cli  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _load(self) -> None:
        if self._nlp is not None:
            return
        import spacy
        try:
            self._nlp = spacy.load(self._model_name)
        except OSError:
            import spacy.cli
            spacy.cli.download(self._model_name)
            self._nlp = spacy.load(self._model_name)

    def _map_label(self, spacy_label: str) -> EntityType:
        mapping = {
            "ORG": EntityType.ORGANIZATION,
            "PERSON": EntityType.PERSON,
            "DATE": EntityType.DATE,
            "MONEY": EntityType.AMOUNT,
            "PERCENT": EntityType.PERCENTAGE,
            "GPE": EntityType.ORGANIZATION,
            "LAW": EntityType.REGULATION_ID,
            "STATUTE": EntityType.STATUTE,
            "PRODUCT": EntityType.OTHER,
            "EVENT": EntityType.OTHER,
            "WORK_OF_ART": EntityType.OTHER,
            "LOC": EntityType.ADDRESS,
            "FAC": EntityType.ADDRESS,
        }
        return mapping.get(spacy_label, EntityType.OTHER)

    async def extract(self, text: str, **kwargs: Any) -> NerResult:
        self._load()

        labels = kwargs.get("labels", None)
        doc = self._nlp(text)

        entities: list[ExtractedEntity] = []
        for ent in doc.ents:
            entity_type = self._map_label(ent.label_)
            if labels and entity_type.value not in labels:
                continue
            entities.append(
                ExtractedEntity(
                    id=f"ent-{len(entities) + 1}",
                    type=entity_type,
                    text=ent.text,
                    confidence=float(ent._.confidence) if hasattr(ent._, "confidence") else 0.9,
                    metadata={"label": ent.label_, "start": ent.start_char, "end": ent.end_char},
                )
            )

        for etype, keywords in FINANCIAL_ENTITY_KEYWORDS.items():
            for keyword in keywords:
                idx = text.lower().find(keyword)
                if idx != -1:
                    phrase = text[idx: idx + 80].split(".")[0]
                    already_exists = any(
                        keyword in e.text.lower() for e in entities
                    )
                    if not already_exists:
                        entities.append(
                            ExtractedEntity(
                                id=f"ent-{len(entities) + 1}",
                                type=etype,
                                text=phrase.strip()[:100],
                                confidence=0.5,
                                metadata={"keyword_match": keyword, "match_start": idx},
                            )
                        )

        overall_conf = (
            sum(e.confidence for e in entities) / len(entities)
            if entities
            else 0.0
        )
        return NerResult(entities=entities, overall_confidence=overall_conf)


class HuggingFaceNerEngine(NerEngine):
    """NER engine via HuggingFace token-classification pipeline.

    Args:
        model_name: HuggingFace model ID (default financial NER model).
        device: Torch device.
    """

    def __init__(
        self,
        model_name: str = "Jean-Baptiste/roberta-large-ner-english",
        device: int = -1,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._pipeline = None
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return f"hf-ner:{self._model_name}"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        from transformers import pipeline

        self._pipeline = pipeline(
            "token-classification",
            model=self._model_name,
            aggregation_strategy="simple",
            device=self._device,
        )

    async def extract(self, text: str, **kwargs: Any) -> NerResult:
        self._load()

        results = self._pipeline(text)
        entities: list[ExtractedEntity] = []

        for item in results:
            entity_type = self._map_label(item["entity_group"])
            entities.append(
                ExtractedEntity(
                    id=f"ent-{len(entities) + 1}",
                    type=entity_type,
                    text=item["word"],
                    confidence=float(item["score"]),
                    metadata={
                        "start": item["start"],
                        "end": item["end"],
                        "entity_group": item["entity_group"],
                    },
                )
            )

        overall_conf = (
            sum(e.confidence for e in entities) / len(entities)
            if entities
            else 0.0
        )
        return NerResult(entities=entities, overall_confidence=overall_conf)

    @staticmethod
    def _map_label(label: str) -> EntityType:
        mapping = {
            "ORG": EntityType.ORGANIZATION,
            "PER": EntityType.PERSON,
            "PERSON": EntityType.PERSON,
            "DATE": EntityType.DATE,
            "MONEY": EntityType.AMOUNT,
            "PERCENT": EntityType.PERCENTAGE,
            "GPE": EntityType.ADDRESS,
            "LAW": EntityType.REGULATION_ID,
            "STATUTE": EntityType.STATUTE,
            "MISC": EntityType.OTHER,
        }
        return mapping.get(label, EntityType.OTHER)
