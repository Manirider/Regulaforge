"""
Relation extraction between entities identified in documents.

Combines rule-based (co-occurrence, distance) and ML-based approaches.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from regulaforge.document_intelligence.domain.enums import EntityType
from regulaforge.document_intelligence.domain.models import ExtractedEntity, ExtractedRelation

RELATION_RULES: list[tuple[EntityType, str, EntityType]] = [
    (EntityType.REGULATION_ID, "AMENDS", EntityType.REGULATION_ID),
    (EntityType.REGULATION_ID, "SUPERSEDES", EntityType.REGULATION_ID),
    (EntityType.REGULATION_ID, "REFERENCES", EntityType.SECTION_NUMBER),
    (EntityType.ORGANIZATION, "ISSUES", EntityType.REGULATION_ID),
    (EntityType.ORGANIZATION, "ISSUES", EntityType.GUIDELINE),
    (EntityType.AMOUNT, "THRESHOLD_FOR", EntityType.SECTION_NUMBER),
    (EntityType.DATE, "EFFECTIVE_FROM", EntityType.REGULATION_ID),
    (EntityType.DATE, "EFFECTIVE_FROM", EntityType.SECTION_NUMBER),
]


@dataclass
class RelationResult:
    relations: list[ExtractedRelation] = field(default_factory=list)
    overall_confidence: float = 0.0


class RelationExtractor(ABC):
    @abstractmethod
    async def extract(
        self, entities: list[ExtractedEntity], text: str, **kwargs: Any
    ) -> RelationResult:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class RuleBasedRelationExtractor(RelationExtractor):
    """Extracts relations using co-occurrence within sentence windows and
    known regulatory relation patterns."""

    def __init__(self, max_distance: int = 150) -> None:
        self._max_distance = max_distance
        self._available: bool = True

    @property
    def name(self) -> str:
        return "rule-based"

    async def is_available(self) -> bool:
        return True

    async def extract(
        self, entities: list[ExtractedEntity], text: str, **kwargs: Any
    ) -> RelationResult:
        relations: list[ExtractedRelation] = []

        for i, src in enumerate(entities):
            for dst in entities[i + 1:]:
                rel_type = self._match_rule(src.type, dst.type)
                if rel_type and self._within_distance(src, dst):
                    relations.append(
                        ExtractedRelation(
                            id=f"rel-{len(relations) + 1}",
                            source_id=src.id,
                            target_id=dst.id,
                            relation_type=rel_type,
                            confidence=0.7,
                            metadata={
                                "src_type": src.type.value,
                                "dst_type": dst.type.value,
                                "src_text": src.text[:50],
                                "dst_text": dst.text[:50],
                            },
                        )
                    )

        overall_conf = (
            sum(r.confidence for r in relations) / len(relations)
            if relations
            else 0.0
        )
        return RelationResult(relations=relations, overall_confidence=overall_conf)

    def _within_distance(self, a: ExtractedEntity, b: ExtractedEntity) -> bool:
        pos_a = a.metadata.get("start") if isinstance(a.metadata, dict) else None
        pos_b = b.metadata.get("start") if isinstance(b.metadata, dict) else None
        if pos_a is not None and pos_b is not None:
            return abs(int(pos_a) - int(pos_b)) <= self._max_distance
        return True

    @staticmethod
    def _match_rule(src_type: EntityType, dst_type: EntityType) -> str | None:
        for st, rel, dt in RELATION_RULES:
            if st == src_type and dt == dst_type:
                return rel
        return None
