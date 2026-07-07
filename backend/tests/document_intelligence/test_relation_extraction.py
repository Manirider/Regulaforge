from __future__ import annotations

from uuid import uuid4

import pytest
from regulaforge.document_intelligence.application.relation_extraction import RelationExtractionService
from regulaforge.document_intelligence.domain.models import (
    EntityType,
)
from regulaforge.document_intelligence.application.models import (
    ConfidenceScore,
    ExtractedEntity,
)
from regulaforge.document_intelligence.application.enums import (
    RelationType,
)


class TestRelationExtractionService:
    @pytest.fixture
    def extractor(self) -> RelationExtractionService:
        return RelationExtractionService()

    def _make_entity(self, text: str, entity_type: EntityType, start: int = 0) -> ExtractedEntity:
        return ExtractedEntity(
            id=uuid4(),
            entity_type=entity_type,
            text=text,
            start_char=start,
            end_char=start + len(text),
            page=1,
            confidence=ConfidenceScore(value=0.9, model="test"),
        )

    @pytest.mark.asyncio
    async def test_empty_entities(self, extractor) -> None:
        relations = await extractor.extract([], "text")
        assert relations == []

    @pytest.mark.asyncio
    async def test_cooccurrence_organization_jurisdiction(self, extractor) -> None:
        entities = [
            self._make_entity("SEBI", EntityType.ORGANIZATION, start=0),
            self._make_entity("India", EntityType.JURISDICTION, start=10),
        ]
        relations = await extractor.extract(entities, "SEBI India")
        assert len(relations) >= 1

    @pytest.mark.asyncio
    async def test_compliance_requires(self, extractor) -> None:
        entities = [
            self._make_entity("SEBI", EntityType.ORGANIZATION, start=0),
            self._make_entity("shall comply", EntityType.COMPLIANCE_ACTION, start=20),
        ]
        relations = await extractor.extract(entities, "SEBI shall comply with these rules")
        assert len(relations) >= 1

    @pytest.mark.asyncio
    async def test_returns_relation_type(self, extractor) -> None:
        entities = [
            self._make_entity("RBI", EntityType.ORGANIZATION, start=0),
            self._make_entity("penalty", EntityType.PENALTY, start=20),
        ]
        relations = await extractor.extract(entities, "RBI imposed penalty of Rs. 1,00,000")
        assert len(relations) >= 1
        assert all(isinstance(r.relation_type, RelationType) for r in relations)
