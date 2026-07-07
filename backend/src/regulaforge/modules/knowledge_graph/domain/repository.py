from __future__ import annotations

from typing import Optional

from regulaforge.modules.knowledge_graph.domain.models import Entity, GraphQuery, Relationship


class EntityRepository:
    async def find_by_id(self, entity_id: str) -> Optional[Entity]:
        raise NotImplementedError

    async def find_by_type(self, entity_type: str, skip: int = 0, limit: int = 100) -> list[Entity]:
        raise NotImplementedError

    async def search(self, query: str, limit: int = 20) -> list[Entity]:
        raise NotImplementedError

    async def save(self, entity: Entity) -> Entity:
        raise NotImplementedError

    async def delete(self, entity_id: str) -> None:
        raise NotImplementedError


class RelationshipRepository:
    async def find_by_id(self, relationship_id: str) -> Optional[Relationship]:
        raise NotImplementedError

    async def find_by_source(self, source_id: str) -> list[Relationship]:
        raise NotImplementedError

    async def find_by_target(self, target_id: str) -> list[Relationship]:
        raise NotImplementedError

    async def find_by_type(self, rel_type: str) -> list[Relationship]:
        raise NotImplementedError

    async def save(self, relationship: Relationship) -> Relationship:
        raise NotImplementedError

    async def delete(self, relationship_id: str) -> None:
        raise NotImplementedError
