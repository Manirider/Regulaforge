from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from regulaforge.document_intelligence.application.enums import RelationType
from regulaforge.document_intelligence.application.models import (
    ConfidenceScore,
    ExtractedEntity,
    Relation,
)
from regulaforge.document_intelligence.domain.enums import EntityType

logger = logging.getLogger(__name__)


class RelationExtractionService:
    PATTERN_RULES: dict[RelationType, list[tuple[str, EntityType, EntityType]]] = {  # noqa: RUF012
        RelationType.REFERENCES: [
            (r"(in accordance with|pursuant to|under|as per|according to)", EntityType.REGULATION, EntityType.REGULATION),  # noqa: E501
            (r"(as defined in|defined in)", EntityType.TERM, EntityType.REGULATION),
            (r"(referred to in|mentioned in)", EntityType.REGULATION, EntityType.REGULATION),
        ],
        RelationType.AMENDS: [
            (r"(amends|amended by|amending|modified by|substituted by)", EntityType.REGULATION, EntityType.REGULATION),
        ],
        RelationType.SUPERSEDES: [
            (r"(supersedes|superseded by|replaces|replaced by|revoked by)", EntityType.REGULATION, EntityType.REGULATION),  # noqa: E501
        ],
        RelationType.REQUIRES: [
            (r"(shall|must|required to|obligated to)", EntityType.REGULATION, EntityType.COMPLIANCE_ACTION),
        ],
        RelationType.PENALIZES: [
            (r"(penalty|liable to|punishable|fine|imprisonment)", EntityType.REGULATION, EntityType.PENALTY),
        ],
        RelationType.DEFINES: [
            (r"(means|is defined as|refers to|shall include|shall mean)", EntityType.TERM, EntityType.DEFINITION),
        ],
    }

    CO_OCCURRENCE_DISTANCE = 500

    async def extract(
        self,
        entities: list[ExtractedEntity],
        text: str,
    ) -> list[Relation]:
        relations: list[Relation] = []
        seen: set[tuple[Any, ...]] = set()

        pattern_relations = self._extract_pattern_based(text, entities)
        relations.extend(pattern_relations)
        for r in pattern_relations:
            seen.add((r.source_entity_id, r.target_entity_id, r.relation_type.value))

        cooccur_relations = self._extract_cooccurrence_based(entities, text, seen)
        relations.extend(cooccur_relations)

        logger.info("Relation extraction: %d relations (%d pattern, %d co-occurrence)", len(relations), len(pattern_relations), len(cooccur_relations))  # noqa: E501
        return relations

    def _extract_pattern_based(
        self,
        text: str,
        entities: list[ExtractedEntity],
    ) -> list[Relation]:
        relations: list[Relation] = []
        text_lower = text.lower()

        for rel_type, patterns in self.PATTERN_RULES.items():
            for pattern, src_type, tgt_type in patterns:
                for match in re.finditer(pattern, text_lower):
                    match_pos = match.start()

                    src_candidates = [
                        e for e in entities
                        if e.entity_type == src_type
                        and abs(e.start_char - match_pos) < 200
                        and e.start_char < match_pos
                    ]
                    tgt_candidates = [
                        e for e in entities
                        if e.entity_type == tgt_type
                        and abs(e.start_char - match_pos) < 200
                        and e.start_char > match_pos + len(match.group(0))
                    ]

                    for src in src_candidates[:2]:
                        for tgt in tgt_candidates[:2]:
                            if src.id != tgt.id and src.start_char < tgt.start_char:
                                relations.append(
                                    Relation(
                                        id=uuid4(),
                                        relation_type=rel_type,
                                        source_entity_id=src.id,
                                        target_entity_id=tgt.id,
                                        confidence=ConfidenceScore(value=0.7, model="pattern_matcher"),
                                        metadata={"trigger": match.group(0), "pattern": pattern},
                                    )
                                )
        return relations

    def _extract_cooccurrence_based(
        self,
        entities: list[ExtractedEntity],
        text: str,
        seen: set[tuple[Any, ...]],
    ) -> list[Relation]:
        relations: list[Relation] = []
        sorted_entities = sorted(entities, key=lambda e: e.start_char)

        for i in range(len(sorted_entities)):
            for j in range(i + 1, len(sorted_entities)):
                src = sorted_entities[i]
                tgt = sorted_entities[j]
                distance = tgt.start_char - src.end_char

                if distance > self.CO_OCCURRENCE_DISTANCE or distance < 0:
                    continue

                if (src.id, tgt.id, RelationType.REFERENCES.value) in seen:
                    continue

                rel_type = self._infer_relation_type(src.entity_type, tgt.entity_type)

                window_text = text[src.start_char:tgt.end_char].lower()
                confidence = 0.4
                if any(p in window_text for p in ["shall", "must", "required"]):
                    confidence += 0.15
                    rel_type = RelationType.REQUIRES
                if any(p in window_text for p in ["penalty", "fine", "punishable"]):
                    confidence += 0.15
                    rel_type = RelationType.PENALIZES
                if re.search(r"in accordance with|pursuant to|under\s+", window_text):
                    confidence += 0.1

                relations.append(
                    Relation(
                        id=uuid4(),
                        relation_type=rel_type,
                        source_entity_id=src.id,
                        target_entity_id=tgt.id,
                        confidence=ConfidenceScore(value=min(confidence, 0.95), model="cooccurrence"),
                        metadata={"distance": distance, "window_text": window_text[:100]},
                    )
                )

        return relations

    def _infer_relation_type(self, src_type: EntityType, tgt_type: EntityType) -> RelationType:
        hierarchy: dict[EntityType, int] = {
            EntityType.REGULATION: 5,
            EntityType.STATUTE: 5,
            EntityType.ORGANIZATION: 4,
            EntityType.SECTION: 3,
            EntityType.CLAUSE_REF: 3,
            EntityType.COMPLIANCE_ACTION: 2,
            EntityType.PENALTY: 2,
            EntityType.DEFINITION: 1,
            EntityType.TERM: 1,
        }
        src_rank = hierarchy.get(src_type, 0)
        tgt_rank = hierarchy.get(tgt_type, 0)
        if src_rank > tgt_rank:
            return RelationType.REFERENCES
        if tgt_type in (EntityType.PENALTY,):
            return RelationType.PENALIZES
        if tgt_type == EntityType.COMPLIANCE_ACTION:
            return RelationType.REQUIRES
        return RelationType.REFERENCES
