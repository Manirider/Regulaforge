from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.graphrag.domain.enums import GraphRelationshipType
from regulaforge.graphrag.domain.models import (
    GraphPath,
    GraphQuery,
    TraversalConfig,
)

logger = logging.getLogger(__name__)


class GraphTraversalService:
    def __init__(self, neo4j_client: Any) -> None:
        self.neo4j = neo4j_client

    async def traverse_from_entity(
        self,
        entity_name: str,
        config: Optional[TraversalConfig] = None,
    ) -> list[GraphPath]:
        if config is None:
            config = TraversalConfig()

        query = GraphQuery(
            entity_names=[entity_name],
            max_depth=config.max_depth,
            limit=config.max_branches,
        )
        paths = await self.neo4j.query_graph(query)
        logger.info(
            "Traversal from '%s': depth=%d, paths=%d",
            entity_name,
            config.max_depth,
            len(paths),
        )
        return list(paths)

    async def traverse_between(
        self,
        source_entity: str,
        target_entity: str,
        max_depth: int = 4,
    ) -> Optional[GraphPath]:
        async with self.neo4j._session() as session:
            result = await session.run(
                """
                MATCH path = shortestPath(
                    (a:Entity {name: $source})-[*1..$max_depth]-(b:Entity {name: $target})
                )
                RETURN path
                """,
                source=source_entity,
                target=target_entity,
                max_depth=max_depth,
            )
            record = await result.single()
            if record and record.get("path"):
                path_data = record["path"]
                nodes = [
                    {"id": n.get("id"), "labels": list(n.labels), "props": dict(n)}
                    for n in path_data.nodes
                ]
                edges = [
                    {
                        "source": e.start_node.get("id"),
                        "target": e.end_node.get("id"),
                        "type": e.type,
                    }
                    for e in path_data.relationships
                ]
                return GraphPath(
                    nodes=nodes,
                    edges=edges,
                    length=len(edges),
                )
            return None

    async def get_entity_neighborhood(
        self,
        entity_name: str,
        relationship_types: Optional[list[GraphRelationshipType]] = None,
        max_depth: int = 2,
    ) -> dict[str, Any]:
        entities = await self.neo4j.get_related_entities(
            entity_name,
            relationship_types=relationship_types,
            max_depth=max_depth,
        )

        chunks = await self.neo4j.get_chunks_for_entities(
            [e["id"] for e in entities]
        )

        return {
            "entity_name": entity_name,
            "related_entities": len(entities),
            "related_chunks": len(chunks),
            "entities": entities,
            "chunks": chunks,
        }

    async def get_subgraph(
        self,
        entity_names: list[str],
        max_depth: int = 3,
    ) -> list[GraphPath]:
        query = GraphQuery(
            entity_names=entity_names,
            max_depth=max_depth,
            limit=100,
        )
        paths = await self.neo4j.query_graph(query)
        return list(paths)
