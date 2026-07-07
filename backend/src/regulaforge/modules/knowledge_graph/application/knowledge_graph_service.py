from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.common.exceptions import NotFoundError
from regulaforge.modules.knowledge_graph.domain.models import Entity, GraphQuery, Relationship
from regulaforge.modules.knowledge_graph.domain.repository import EntityRepository, RelationshipRepository

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    def __init__(
        self,
        entity_repo: EntityRepository,
        relationship_repo: RelationshipRepository,
    ) -> None:
        self._entity_repo = entity_repo
        self._relationship_repo = relationship_repo

    async def get_entity(self, entity_id: str) -> Entity:
        entity = await self._entity_repo.find_by_id(entity_id)
        if not entity:
            raise NotFoundError(f"Entity {entity_id} not found")
        return entity

    async def list_entities(self, entity_type: Optional[str] = None, skip: int = 0, limit: int = 100) -> tuple[list[Entity], int]:
        if entity_type:
            entities = await self._entity_repo.find_by_type(entity_type, skip, limit)
        else:
            entities = await self._entity_repo.find_by_type("", skip, limit)
        total = len(entities)
        return entities, total

    async def create_entity(self, entity: Entity) -> Entity:
        return await self._entity_repo.save(entity)

    async def update_entity(self, entity_id: str, updates: dict[str, Any]) -> Entity:
        entity = await self.get_entity(entity_id)
        for key, value in updates.items():
            if hasattr(entity, key) and key not in ("id", "created_at"):
                setattr(entity, key, value)
        return await self._entity_repo.save(entity)

    async def delete_entity(self, entity_id: str) -> None:
        entity = await self.get_entity(entity_id)
        await self._entity_repo.delete(entity_id)

    async def search_entities(self, query: str, limit: int = 20) -> list[Entity]:
        return await self._entity_repo.search(query, limit)

    async def get_relationships(self, entity_id: str) -> list[Relationship]:
        outgoing = await self._relationship_repo.find_by_source(entity_id)
        incoming = await self._relationship_repo.find_by_target(entity_id)
        return outgoing + incoming

    async def create_relationship(self, relationship: Relationship) -> Relationship:
        source = await self._entity_repo.find_by_id(relationship.source_id)
        if not source:
            raise NotFoundError(f"Source entity {relationship.source_id} not found")
        target = await self._entity_repo.find_by_id(relationship.target_id)
        if not target:
            raise NotFoundError(f"Target entity {relationship.target_id} not found")
        return await self._relationship_repo.save(relationship)

    async def delete_relationship(self, relationship_id: str) -> None:
        existing = await self._relationship_repo.find_by_id(relationship_id)
        if not existing:
            raise NotFoundError(f"Relationship {relationship_id} not found")
        await self._relationship_repo.delete(relationship_id)

    async def traverse(self, query: GraphQuery) -> dict[str, Any]:
        entities: dict[str, Entity] = {}
        relationships: list[Relationship] = []

        if query.entity_type:
            start = await self._entity_repo.find_by_type(query.entity_type.value, 0, query.limit)
        else:
            start = await self._entity_repo.find_by_type("", 0, query.limit)

        for entity in start:
            entities[entity.id] = entity
            rels = await self._relationship_repo.find_by_source(entity.id)
            for rel in rels:
                if query.relationship_type is None or rel.type == query.relationship_type:
                    relationships.append(rel)
                    target = await self._entity_repo.find_by_id(rel.target_id)
                    if target:
                        entities[target.id] = target

        return {
            "entities": list(entities.values()),
            "relationships": relationships,
            "count": len(entities),
        }
