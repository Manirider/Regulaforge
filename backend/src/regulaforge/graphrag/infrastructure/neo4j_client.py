from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional

from regulaforge.graphrag.domain.enums import (
    GraphRelationshipType,
)
from regulaforge.graphrag.domain.models import (
    ChunkNode,
    DocumentNode,
    EntityNode,
    GraphPath,
    GraphQuery,
    RelationshipEdge,
    TemporalEvent,
    TemporalQuery,
)

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._driver: Any = None

    async def connect(self) -> None:
        for attempt in range(self.max_retries):
            try:
                from neo4j import AsyncGraphDatabase

                self._driver = AsyncGraphDatabase.driver(
                    self.uri, auth=(self.user, self.password)
                )
                await self._driver.verify_connectivity()
                logger.info("Connected to Neo4j at %s", self.uri)
                return
            except Exception as exc:
                logger.warning(
                    "Neo4j connect attempt %d/%d failed: %s",
                    attempt + 1,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(self.retry_delay * (2**attempt))
                else:
                    raise

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def _session(self) -> AsyncGenerator[Any, None]:
        if not self._driver:
            raise RuntimeError("Neo4j not connected")
        async with self._driver.session(database=self.database) as session:
            yield session

    async def create_document_node(self, doc: DocumentNode) -> None:
        async with self._session() as session:
            await session.run(
                """
                MERGE (d:Document {id: $id})
                SET d.title = $title,
                    d.source = $source,
                    d.doc_type = $doc_type,
                    d.jurisdiction = $jurisdiction,
                    d.regulatory_body = $regulatory_body,
                    d.published_date = $published_date,
                    d.created_at = $created_at
                """,
                id=doc.id,
                title=doc.title,
                source=doc.source,
                doc_type=doc.doc_type,
                jurisdiction=doc.jurisdiction,
                regulatory_body=doc.regulatory_body,
                published_date=doc.published_date.isoformat() if doc.published_date else None,
                created_at=doc.created_at.isoformat(),
            )

    async def create_chunk_node(self, chunk: ChunkNode) -> None:
        async with self._session() as session:
            await session.run(
                """
                MERGE (c:Chunk {id: $id})
                SET c.document_id = $document_id,
                    c.text = $text,
                    c.chunk_index = $chunk_index,
                    c.page_number = $page_number,
                    c.heading = $heading
                """,
                id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                heading=chunk.heading,
            )

    async def create_entity_node(self, entity: EntityNode) -> None:
        async with self._session() as session:
            await session.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name = $name,
                    e.category = $category,
                    e.aliases = $aliases,
                    e.description = $description,
                    e.first_seen = $first_seen,
                    e.last_seen = $last_seen
                """,
                id=entity.id,
                name=entity.name,
                category=entity.category.value,
                aliases=entity.aliases,
                description=entity.description,
                first_seen=entity.first_seen.isoformat() if entity.first_seen else None,
                last_seen=entity.last_seen.isoformat() if entity.last_seen else None,
            )

    async def create_relationship(self, edge: RelationshipEdge) -> None:
        async with self._session() as session:
            await session.run(
                f"""
                MATCH (a {{id: $source_id}})
                MATCH (b {{id: $target_id}})
                MERGE (a)-[r:{edge.relationship_type.value}]->(b)
                SET r.weight = $weight,
                    r.confidence = $confidence,
                    r.temporal_context = $temporal_context
                """,
                source_id=edge.source_id,
                target_id=edge.target_id,
                weight=edge.weight,
                confidence=edge.confidence,
                temporal_context=edge.temporal_context,
            )

    async def create_temporal_event(self, event: TemporalEvent) -> None:
        async with self._session() as session:
            await session.run(
                """
                MERGE (te:TemporalEvent {id: $id})
                SET te.name = $name,
                    te.date = $date,
                    te.end_date = $end_date,
                    te.description = $description,
                    te.event_type = $event_type
                """,
                id=event.id,
                name=event.name,
                date=event.date.isoformat(),
                end_date=event.end_date.isoformat() if event.end_date else None,
                description=event.description,
                event_type=event.event_type,
            )
            for entity_id in event.entity_ids:
                await session.run(
                    """
                    MATCH (te:TemporalEvent {id: $event_id})
                    MATCH (e {id: $entity_id})
                    MERGE (te)-[:INVOLVES]->(e)
                    """,
                    event_id=event.id,
                    entity_id=entity_id,
                )

    async def link_chunk_to_document(self, chunk_id: str, doc_id: str) -> None:
        async with self._session() as session:
            await session.run(
                """
                MATCH (c:Chunk {id: $chunk_id})
                MATCH (d:Document {id: $doc_id})
                MERGE (d)-[:CONTAINS]->(c)
                """,
                chunk_id=chunk_id,
                doc_id=doc_id,
            )

    async def link_entity_to_chunk(
        self, entity_id: str, chunk_id: str, confidence: float = 1.0
    ) -> None:
        async with self._session() as session:
            await session.run(
                """
                MATCH (e:Entity {id: $entity_id})
                MATCH (c:Chunk {id: $chunk_id})
                MERGE (c)-[:HAS_ENTITY {confidence: $confidence}]->(e)
                """,
                entity_id=entity_id,
                chunk_id=chunk_id,
                confidence=confidence,
            )

    async def link_entities(self, edge: RelationshipEdge) -> None:
        await self.create_relationship(edge)

    async def query_graph(self, query: GraphQuery) -> list[GraphPath]:
        conditions = []
        params: dict[str, Any] = {}

        if query.entity_names:
            conditions.append("e.name IN $entity_names")
            params["entity_names"] = query.entity_names

        if query.entity_categories:
            conditions.append("e.category IN $categories")
            params["categories"] = [c.value for c in query.entity_categories]

        if query.min_confidence > 0:
            conditions.append("r.confidence >= $min_conf")
            params["min_conf"] = query.min_confidence

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with self._session() as session:
            result = await session.run(
                f"""
                MATCH (e:Entity)-[r]-(c:Chunk)
                {where_clause}
                WITH e, r, c
                OPTIONAL MATCH path = (c)-[*1..{query.max_depth}]-(connected)
                RETURN path, e, r, c
                LIMIT $limit
                """,
                limit=query.limit,
                **params,
            )
            paths = []
            async for record in result:
                path_data = record.get("path")
                if path_data:
                    nodes = [
                        {"id": n.get("id"), "labels": list(n.labels), "props": dict(n)}
                        for n in path_data.nodes
                    ]
                    edges = [
                        {
                            "source": e.start_node.get("id"),
                            "target": e.end_node.get("id"),
                            "type": e.type,
                            "props": dict(e),
                        }
                        for e in path_data.relationships
                    ]
                    paths.append(
                        GraphPath(
                            nodes=nodes,
                            edges=edges,
                            length=len(edges),
                        )
                    )
            return paths

    async def get_related_entities(
        self,
        entity_name: str,
        relationship_types: Optional[list[GraphRelationshipType]] = None,
        max_depth: int = 2,
    ) -> list[dict[str, Any]]:
        rel_filter = ""
        params: dict[str, Any] = {"entity_name": entity_name, "max_depth": max_depth}
        if relationship_types:
            types = [r.value for r in relationship_types]
            rel_filter = "WHERE type(r) IN $rel_types"
            params["rel_types"] = types

        async with self._session() as session:
            result = await session.run(
                f"""
                MATCH (e:Entity {{name: $entity_name}})-[r *1..$max_depth]-(connected)
                {rel_filter}
                RETURN connected, r
                LIMIT 50
                """,
                **params,
            )
            entities = []
            async for record in result:
                connected = record.get("connected")
                if connected:
                    entities.append(
                        {
                            "id": connected.get("id"),
                            "name": connected.get("name"),
                            "category": connected.get("category"),
                            "labels": list(connected.labels),
                        }
                    )
            return entities

    async def get_chunks_for_entities(
        self, entity_ids: list[str]
    ) -> list[dict[str, Any]]:
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (c:Chunk)-[:HAS_ENTITY]->(e:Entity)
                WHERE e.id IN $entity_ids
                RETURN DISTINCT c.id as chunk_id, c.text as text,
                       c.document_id as document_id, c.chunk_index as chunk_index,
                       collect(e.name) as entities
                """,
                entity_ids=entity_ids,
            )
            return [dict(record) async for record in result]

    async def temporal_graph_query(
        self, query: TemporalQuery
    ) -> list[dict[str, Any]]:
        async with self._session() as session:
            if query.entity_names and query.start_date:
                result = await session.run(
                    """
                    MATCH (te:TemporalEvent)
                    WHERE te.date >= $start_date
                    AND ($end_date IS NULL OR te.date <= $end_date)
                    OPTIONAL MATCH (te)-[:INVOLVES]->(e:Entity)
                    WHERE e.name IN $entity_names
                    RETURN te, collect(DISTINCT e) as entities
                    ORDER BY te.date
                    LIMIT $limit
                    """,
                    start_date=query.start_date.isoformat(),
                    end_date=query.end_date.isoformat() if query.end_date else None,
                    entity_names=query.entity_names or [],
                    limit=query.limit,
                )
            else:
                result = await session.run(
                    """
                    MATCH (te:TemporalEvent)
                    WHERE ($start_date IS NULL OR te.date >= $start_date)
                    AND ($end_date IS NULL OR te.date <= $end_date)
                    OPTIONAL MATCH (te)-[:INVOLVES]->(e:Entity)
                    RETURN te, collect(DISTINCT e) as entities
                    ORDER BY te.date
                    LIMIT $limit
                    """,
                    start_date=query.start_date.isoformat() if query.start_date else None,
                    end_date=query.end_date.isoformat() if query.end_date else None,
                    limit=query.limit,
                )
            return [dict(record) async for record in result]

    async def delete_all(self) -> None:
        async with self._session() as session:
            await session.run("MATCH (n) DETACH DELETE n")

    async def create_constraints(self) -> None:
        async with self._session() as session:
            for label in ["Document", "Chunk", "Entity", "TemporalEvent"]:
                await session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
                )
            await session.run(
                "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.name)"
            )
            await session.run(
                "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.category)"
            )
            await session.run(
                "CREATE INDEX IF NOT EXISTS FOR (n:TemporalEvent) ON (n.date)"
            )
