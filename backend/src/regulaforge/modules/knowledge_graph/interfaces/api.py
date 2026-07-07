from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response

from regulaforge.common.exceptions import NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.knowledge_graph.application.knowledge_graph_service import KnowledgeGraphService
from regulaforge.modules.knowledge_graph.domain.models import Entity, GraphQuery, Relationship

logger = logging.getLogger(__name__)


def create_knowledge_graph_router(
    kg_service: Optional[KnowledgeGraphService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/knowledge-graph",
        tags=["Knowledge Graph"],
        dependencies=dependencies or [],
    )

    @router.get("/entities")
    async def list_entities(
        entity_type: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
    ) -> dict[str, Any]:
        entities, total = await kg_service.list_entities(entity_type, skip, limit)
        return create_response(data={
            "items": [{
                "id": e.id,
                "type": e.type.value,
                "name": e.name,
                "description": e.description,
                "source": e.source,
            } for e in entities],
            "total": total,
        })

    @router.post("/entities", status_code=status.HTTP_201_CREATED)
    async def create_entity(body: Entity) -> dict[str, Any]:
        entity = await kg_service.create_entity(body)
        return create_response(data={"id": entity.id, "name": entity.name})

    @router.get("/entities/search")
    async def search_entities(q: str = Query(""), limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
        entities = await kg_service.search_entities(q, limit)
        return create_response(data=[{
            "id": e.id,
            "type": e.type.value,
            "name": e.name,
        } for e in entities])

    @router.get("/entities/{entity_id}")
    async def get_entity(entity_id: str) -> dict[str, Any]:
        try:
            entity = await kg_service.get_entity(entity_id)
            return create_response(data={
                "id": entity.id,
                "type": entity.type.value,
                "name": entity.name,
                "description": entity.description,
                "properties": entity.properties,
                "source": entity.source,
                "created_at": entity.created_at.isoformat(),
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.put("/entities/{entity_id}")
    async def update_entity(entity_id: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            entity = await kg_service.update_entity(entity_id, body)
            return create_response(data={"id": entity.id})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_entity(entity_id: str) -> Response:
        try:
            await kg_service.delete_entity(entity_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.get("/entities/{entity_id}/relationships")
    async def get_entity_relationships(entity_id: str) -> dict[str, Any]:
        rels = await kg_service.get_relationships(entity_id)
        return create_response(data=[{
            "id": r.id,
            "source_id": r.source_id,
            "target_id": r.target_id,
            "type": r.type.value,
            "weight": r.weight,
        } for r in rels])

    @router.post("/relationships", status_code=status.HTTP_201_CREATED)
    async def create_relationship(body: Relationship) -> dict[str, Any]:
        try:
            rel = await kg_service.create_relationship(body)
            return create_response(data={"id": rel.id})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_relationship(relationship_id: str) -> Response:
        try:
            await kg_service.delete_relationship(relationship_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/traverse")
    async def traverse(body: GraphQuery) -> dict[str, Any]:
        result = await kg_service.traverse(body)
        return create_response(data={
            "count": result["count"],
            "entities": [{
                "id": e.id, "type": e.type.value, "name": e.name,
            } for e in result["entities"]],
            "relationships": [{
                "id": r.id, "source_id": r.source_id,
                "target_id": r.target_id, "type": r.type.value,
            } for r in result["relationships"]],
        })

    return router
