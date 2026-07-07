"""Neo4j adapter — infrastructure implementation of the graph repository ports.

Provides async Neo4j connectivity with connection pooling, retry logic,
circuit breaker pattern, health checks, and batch operations.
Implements GraphNodeRepository, GraphRelationshipRepository, and
GraphQueryRepository interfaces.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
    TemporalRelationship,
)
from regulaforge.knowledge_graph.domain.repository import (
    ConnectionError,
    EntityNotFoundError,
    GraphNodeRepository,
    GraphQueryRepository,
    GraphRelationshipRepository,
    NodeWithScore,
    QueryExecutionError,
    RepositoryError,
)
from regulaforge.knowledge_graph.infrastructure.cypher_queries import (
    build_create_node_query,
    build_schema_setup_queries,
    build_temporal_filter,
)

logger = get_logger(__name__)


class CircuitBreaker:
    """Simple circuit breaker pattern for Neo4j connections.

    Prevents cascading failures by stopping requests to
    an unresponsive database after a threshold of failures.
    """

    OPEN = "open"
    HALF_OPEN = "half_open"
    CLOSED = "closed"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state: str = self.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None

    def __call__(self, func: Any) -> Any:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if self._state == self.OPEN:
                if time.monotonic() - (self._last_failure_time or 0) > self._recovery_timeout:
                    self._state = self.HALF_OPEN
                    logger.info("Circuit breaker half-open, attempting recovery")
                else:
                    raise ConnectionError("Circuit breaker is OPEN — Neo4j is unavailable")

            try:
                result = await func(*args, **kwargs)
                if self._state == self.HALF_OPEN:
                    self._state = self.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker closed — Neo4j connection recovered")
                return result
            except Exception:
                self._failure_count += 1
                self._last_failure_time = time.monotonic()
                if self._failure_count >= self._failure_threshold:
                    self._state = self.OPEN
                    logger.error(
                        "Circuit breaker opened after %d failures",
                        self._failure_count,
                    )
                raise

        return wrapper


class Neo4jAdapter(
    GraphNodeRepository,
    GraphRelationshipRepository,
    GraphQueryRepository,
):
    """Async Neo4j adapter implementing all graph repository interfaces.

    Manages connection lifecycle, session management, retry logic,
    and maps Neo4j records to domain TemporalNode/TemporalRelationship objects.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._uri = uri or settings.neo4j.uri
        self._user = user or settings.neo4j.user
        self._password = password or settings.neo4j.password
        self._database = database or settings.neo4j.database
        self._max_connection_pool_size = max_connection_pool_size or settings.neo4j.max_connection_pool_size
        self._connection_timeout = connection_timeout or settings.neo4j.connection_timeout
        self._max_retries = max_retries

        self._driver: Optional[Any] = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
        )

        logger.info(
            "Neo4jAdapter initialized",
            extra={
                "uri": self._uri,
                "database": self._database,
                "pool_size": self._max_connection_pool_size,
            },
        )

    async def connect(self) -> None:
        """Initialize the Neo4j driver and establish connection pool."""
        if self._driver:
            return

        try:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                max_connection_pool_size=self._max_connection_pool_size,
                connection_timeout=self._connection_timeout,
            )
            await self._driver.verify_connectivity()
            logger.info("Connected to Neo4j", extra={"uri": self._uri})
        except Exception as e:
            logger.error("Failed to connect to Neo4j: %s", str(e))
            raise ConnectionError(f"Failed to connect to Neo4j at {self._uri}", e)

    async def disconnect(self) -> None:
        """Close the Neo4j driver and release all connections."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Disconnected from Neo4j")

    async def health_check(self) -> dict[str, Any]:
        """Check Neo4j connectivity and return health status."""
        if not self._driver:
            return {"status": "disconnected", "uri": self._uri}

        try:
            await self._driver.verify_connectivity()
            result = await self._execute_read("RETURN 1 AS health")
            return {
                "status": "connected",
                "uri": self._uri,
                "database": self._database,
                "server_ok": bool(result and result[0].get("health") == 1),
            }
        except Exception as e:
            return {
                "status": "error",
                "uri": self._uri,
                "error": str(e),
            }

    async def ensure_schema(self) -> dict[str, Any]:
        """Create indexes and constraints for the knowledge graph schema.

        Runs all schema setup queries idempotently (IF NOT EXISTS).
        Returns a summary of setup results.
        """
        logger.info("Ensuring knowledge graph schema (indexes + constraints)")

        queries = build_schema_setup_queries()
        results: dict[str, Any] = {
            "constraints_created": 0,
            "indexes_created": 0,
            "errors": [],
        }

        for query in queries:
            try:
                if self._driver:
                    session = self._driver.session(database=self._database)
                    try:
                        await session.run(query)
                        is_constraint = "CONSTRAINT" in query
                        if is_constraint:
                            results["constraints_created"] += 1
                        else:
                            results["indexes_created"] += 1
                    finally:
                        await session.close()
            except Exception as e:
                error_msg = f"Schema setup failed for query: {e!s}"
                results["errors"].append(error_msg[:200])
                logger.warning(error_msg)

        results["success"] = len(results["errors"]) == 0
        logger.info(
            "Schema setup complete",
            extra={
                "constraints": results["constraints_created"],
                "indexes": results["indexes_created"],
                "errors": len(results["errors"]),
            },
        )
        return results

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self, write: bool = False) -> AsyncSession:
        """Get a Neo4j session, connecting if needed."""
        if not self._driver:
            await self.connect()

        if not self._driver:
            raise ConnectionError("Neo4j driver is not initialized")

        return self._driver.session(
            database=self._database,
            default_access_mode="WRITE" if write else "READ",
        )

    async def _execute_read(self, query: str, **params: Any) -> list[AsyncRecord]:
        """Execute a read query with retry logic."""
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                session = await self._get_session(write=False)
                try:
                    result = await session.run(query, **params)
                    records = await result.data()
                    return records if records else []
                finally:
                    await session.close()
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    wait = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "Read query attempt %d failed, retrying in %.1fs: %s",
                        attempt, wait, str(e),
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("Read query failed after %d attempts: %s", attempt, str(e))
                    raise QueryExecutionError(str(e), query, e)

        raise QueryExecutionError("Read query failed after all retries", query, last_error)

    async def _execute_write(self, query: str, **params: Any) -> list[AsyncRecord]:
        """Execute a write query with retry logic."""
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                session = await self._get_session(write=True)
                try:
                    result = await session.run(query, **params)
                    records = await result.data()
                    return records if records else []
                finally:
                    await session.close()
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    wait = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "Write query attempt %d failed, retrying in %.1fs: %s",
                        attempt, wait, str(e),
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("Write query failed after %d attempts: %s", attempt, str(e))
                    raise QueryExecutionError(str(e), query, e)

        raise QueryExecutionError("Write query failed after all retries", query, last_error)

    # ------------------------------------------------------------------
    # Record → Domain model mapping
    # ------------------------------------------------------------------

    def _record_to_temporal_node(self, record: Any) -> TemporalNode:
        """Convert a Neo4j record to a TemporalNode domain model."""
        data = record if isinstance(record, dict) else dict(record)

        node_data = data.get("n", data)

        props = dict(node_data) if hasattr(node_data, "get") else dict(node_data)

        node_id = props.get("id")
        if isinstance(node_id, str):
            node_id = UUID(node_id)

        node_type_str = props.get("node_type", "REGULATION")
        try:
            node_type = GraphNodeType(node_type_str)
        except ValueError:
            node_type = GraphNodeType.REGULATION

        labels = props.get("labels", [])
        if isinstance(labels, str):
            labels = [labels]

        properties = {k: v for k, v in props.items() if k not in (
            "id", "node_type", "labels", "valid_from", "valid_to",
            "version", "created_at", "updated_at", "embedding",
        )}

        valid_from = self._parse_datetime(props.get("valid_from"))
        valid_to = self._parse_datetime(props.get("valid_to")) if props.get("valid_to") else None
        created_at = self._parse_datetime(props.get("created_at")) or datetime.now(timezone.utc)
        updated_at = self._parse_datetime(props.get("updated_at")) or datetime.now(timezone.utc)
        version = int(props.get("version", 1))

        embedding = props.get("embedding")
        if embedding is not None and not isinstance(embedding, list):
            embedding = None

        return TemporalNode(
            id=node_id,
            node_type=node_type,
            labels=labels if isinstance(labels, list) else [],
            properties=properties,
            valid_from=valid_from or datetime.now(timezone.utc),
            valid_to=valid_to,
            version=version,
            created_at=created_at,
            updated_at=updated_at,
            embedding=embedding,
        )

    def _record_to_temporal_relationship(self, record: Any) -> TemporalRelationship:
        """Convert a Neo4j record to a TemporalRelationship domain model."""
        data = record if isinstance(record, dict) else dict(record)
        rel_data = data.get("r", data)

        props = dict(rel_data) if hasattr(rel_data, "get") else dict(rel_data)

        rel_id = props.get("id")
        if isinstance(rel_id, str):
            rel_id = UUID(rel_id)

        source_id = props.get("source_id")
        if isinstance(source_id, str):
            source_id = UUID(source_id)

        target_id = props.get("target_id")
        if isinstance(target_id, str):
            target_id = UUID(target_id)

        rel_type_str = props.get("rel_type", "REFERENCES")
        try:
            rel_type = GraphRelationshipType(rel_type_str)
        except ValueError:
            rel_type = GraphRelationshipType.REFERENCES

        rel_properties = props.get("properties", {})
        if not isinstance(rel_properties, dict):
            rel_properties = {}

        valid_from = self._parse_datetime(props.get("valid_from")) or datetime.now(timezone.utc)
        valid_to = self._parse_datetime(props.get("valid_to")) if props.get("valid_to") else None
        created_at = self._parse_datetime(props.get("created_at")) or datetime.now(timezone.utc)
        updated_at = self._parse_datetime(props.get("updated_at")) or datetime.now(timezone.utc)
        version = int(props.get("version", 1))

        return TemporalRelationship(
            id=rel_id,
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            properties=rel_properties if isinstance(rel_properties, dict) else {},
            valid_from=valid_from,
            valid_to=valid_to,
            version=version,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse a datetime from various Neo4j return formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if hasattr(value, "to_native"):
            return value.to_native()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        if isinstance(value, int | float):
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (ValueError, OSError):
                pass
        return None

    # ------------------------------------------------------------------
    # GraphNodeRepository implementation
    # ------------------------------------------------------------------

    async def save(self, node: TemporalNode) -> TemporalNode:
        """Persist a node to Neo4j."""
        logger.debug("Saving node", extra={"node_id": str(node.id), "type": node.node_type.value})

        query = build_create_node_query(node.node_type.value)

        params: dict[str, Any] = {
            "id": str(node.id),
            "node_type": node.node_type.value,
            "labels": node.labels,
            "valid_from": node.valid_from.isoformat(),
            "valid_to": node.valid_to.isoformat() if node.valid_to else None,
            "version": node.version,
            "created_at": node.created_at.isoformat(),
            "updated_at": node.updated_at.isoformat(),
            "embedding": node.embedding,
        }

        for key, value in node.properties.items():
            if isinstance(value, datetime):
                params[key] = value.isoformat()
            elif isinstance(value, list | dict):
                params[key] = str(value) if not isinstance(value, list | dict) else value
            else:
                params[key] = value

        try:
            await self._execute_write(query, **params)
            logger.debug("Node saved successfully", extra={"node_id": str(node.id)})
            return node
        except Exception as e:
            logger.error("Failed to save node: %s", str(e))
            raise RepositoryError(f"Failed to save node {node.id}: {e}", e)

    async def get_by_id(self, node_id: UUID) -> Optional[TemporalNode]:
        """Retrieve a node by ID."""
        logger.debug("Getting node by ID", extra={"node_id": str(node_id)})

        query = "MATCH (n {id: $id}) RETURN n LIMIT 1"
        try:
            records = await self._execute_read(query, id=str(node_id))
            if not records:
                return None
            record = records[0]
            return self._record_to_temporal_node(record)
        except Exception as e:
            logger.error("Failed to get node by ID: %s", str(e))
            raise RepositoryError(f"Failed to get node {node_id}: {e}", e)

    async def get_by_type(
        self,
        node_type: GraphNodeType,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        """Get nodes by type with pagination."""
        logger.debug("Getting nodes by type", extra={"type": node_type.value, "page": page, "page_size": page_size})

        count_query = "MATCH (n {node_type: $node_type}) RETURN count(n) AS total"
        data_query = (
            "MATCH (n {node_type: $node_type}) "
            "RETURN n ORDER BY n.created_at DESC "
            f"SKIP {(page - 1) * page_size} LIMIT {page_size}"
        )

        try:
            count_records = await self._execute_read(count_query, node_type=node_type.value)
            total = count_records[0]["total"] if count_records else 0
            total = int(total)

            data_records = await self._execute_read(data_query, node_type=node_type.value)
            nodes = [self._record_to_temporal_node(r) for r in data_records]

            return nodes, total
        except Exception as e:
            logger.error("Failed to get nodes by type: %s", str(e))
            raise RepositoryError(f"Failed to get nodes by type {node_type.value}: {e}", e)

    async def get_by_label(
        self,
        label: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        """Get nodes by label with pagination."""
        logger.debug("Getting nodes by label", extra={"label": label, "page": page, "page_size": page_size})

        count_query = "MATCH (n) WHERE $label IN n.labels RETURN count(n) AS total"
        data_query = (
            "MATCH (n) WHERE $label IN n.labels "
            "RETURN n ORDER BY n.created_at DESC "
            f"SKIP {(page - 1) * page_size} LIMIT {page_size}"
        )

        try:
            count_records = await self._execute_read(count_query, label=label)
            total = int(count_records[0]["total"]) if count_records else 0

            data_records = await self._execute_read(data_query, label=label)
            nodes = [self._record_to_temporal_node(r) for r in data_records]

            return nodes, total
        except Exception as e:
            logger.error("Failed to get nodes by label: %s", str(e))
            raise RepositoryError(f"Failed to get nodes by label '{label}': {e}", e)

    async def search_embedding(
        self,
        embedding: list[float],
        limit: int = 20,
    ) -> list[NodeWithScore]:
        """Search nodes by embedding vector similarity."""
        logger.debug("Searching by embedding", extra={"limit": limit})

        query = (
            "MATCH (n) WHERE n.embedding IS NOT NULL "
            "WITH n, gds.similarity.cosine(n.embedding, $embedding) AS score "
            "RETURN n, score ORDER BY score DESC LIMIT $limit"
        )

        try:
            records = await self._execute_read(query, embedding=embedding, limit=limit)
            results = []
            for record in records:
                node = self._record_to_temporal_node(record)
                score = float(record.get("score", 0.0)) if isinstance(record, dict) else 0.0
                results.append(NodeWithScore(node=node, score=score))
            return results
        except Exception as e:
            logger.error("Failed to search by embedding: %s", str(e))
            raise RepositoryError(f"Failed to search by embedding: {e}", e)

    async def get_temporal_snapshot(
        self,
        node_id: UUID,
        as_of: datetime,
    ) -> Optional[TemporalNode]:
        """Get node state at a specific point in time."""
        logger.debug("Getting temporal snapshot", extra={
            "node_id": str(node_id),
            "as_of": as_of.isoformat(),
        })

        query = (
            "MATCH (n {id: $id}) "
            f"WHERE {build_temporal_filter('n', 'as_of')} "
            "RETURN n ORDER BY n.version DESC LIMIT 1"
        )

        try:
            records = await self._execute_read(query, id=str(node_id), as_of=as_of.isoformat())
            if not records:
                return None
            return self._record_to_temporal_node(records[0])
        except Exception as e:
            logger.error("Failed to get temporal snapshot: %s", str(e))
            raise RepositoryError(f"Failed to get temporal snapshot for {node_id}: {e}", e)

    async def get_temporal_history(
        self,
        node_id: UUID,
    ) -> list[TemporalNode]:
        """Get all historical versions of a node."""
        logger.debug("Getting temporal history", extra={"node_id": str(node_id)})

        query = "MATCH (n {id: $id}) RETURN n ORDER BY n.valid_from ASC"

        try:
            records = await self._execute_read(query, id=str(node_id))
            return [self._record_to_temporal_node(r) for r in records]
        except Exception as e:
            logger.error("Failed to get temporal history: %s", str(e))
            raise RepositoryError(f"Failed to get temporal history for {node_id}: {e}", e)

    async def soft_delete(self, node_id: UUID) -> None:
        """Soft-delete a node by setting valid_to."""
        logger.info("Soft-deleting node", extra={"node_id": str(node_id)})

        now = datetime.now(timezone.utc).isoformat()
        query = "MATCH (n {id: $id}) WHERE n.valid_to IS NULL SET n.valid_to = datetime($now) RETURN n"

        try:
            records = await self._execute_write(query, id=str(node_id), now=now)
            if not records:
                raise EntityNotFoundError("GraphNode", node_id)
            logger.info("Node soft-deleted", extra={"node_id": str(node_id)})
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to soft-delete node: %s", str(e))
            raise RepositoryError(f"Failed to soft-delete node {node_id}: {e}", e)

    # ------------------------------------------------------------------
    # GraphRelationshipRepository implementation
    # ------------------------------------------------------------------

    async def save(self, relationship: TemporalRelationship) -> TemporalRelationship:
        """Persist a relationship to Neo4j."""
        logger.debug("Saving relationship", extra={"rel_id": str(relationship.id)})

        from regulaforge.knowledge_graph.infrastructure.cypher_queries import CREATE_RELATIONSHIP

        params: dict[str, Any] = {
            "source_id": str(relationship.source_id),
            "target_id": str(relationship.target_id),
            "id": str(relationship.id),
            "rel_type": relationship.rel_type.value,
            "properties": relationship.properties,
            "valid_from": relationship.valid_from.isoformat(),
            "valid_to": relationship.valid_to.isoformat() if relationship.valid_to else None,
            "version": relationship.version,
            "created_at": relationship.created_at.isoformat(),
            "updated_at": relationship.updated_at.isoformat(),
        }

        try:
            records = await self._execute_write(CREATE_RELATIONSHIP, **params)
            if records:
                logger.debug("Relationship saved", extra={"rel_id": str(relationship.id)})
            return relationship
        except Exception as e:
            logger.error("Failed to save relationship: %s", str(e))
            raise RepositoryError(f"Failed to save relationship {relationship.id}: {e}", e)

    async def get_by_id(self, rel_id: UUID) -> Optional[TemporalRelationship]:
        """Retrieve a relationship by ID."""
        logger.debug("Getting relationship by ID", extra={"rel_id": str(rel_id)})

        query = "MATCH ()-[r {id: $id}]-() RETURN r LIMIT 1"
        try:
            records = await self._execute_read(query, id=str(rel_id))
            if not records:
                return None
            return self._record_to_temporal_relationship(records[0])
        except Exception as e:
            logger.error("Failed to get relationship: %s", str(e))
            raise RepositoryError(f"Failed to get relationship {rel_id}: {e}", e)

    async def get_by_source(
        self,
        source_id: UUID,
        rel_type: Optional[GraphRelationshipType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalRelationship], int]:
        """Get relationships by source node."""
        logger.debug("Getting relationships by source", extra={"source_id": str(source_id)})

        if rel_type:
            count_query = (
                "MATCH (source {id: $source_id})-[r {rel_type: $rel_type}]->() "
                "RETURN count(r) AS total"
            )
            data_query = (
                "MATCH (source {id: $source_id})-[r {rel_type: $rel_type}]->(target) "
                "RETURN r, target "
                f"SKIP {(page - 1) * page_size} LIMIT {page_size}"
            )
            params = {"source_id": str(source_id), "rel_type": rel_type.value}
        else:
            count_query = (
                "MATCH (source {id: $source_id})-[r]->() "
                "RETURN count(r) AS total"
            )
            data_query = (
                "MATCH (source {id: $source_id})-[r]->(target) "
                "RETURN r, target "
                f"SKIP {(page - 1) * page_size} LIMIT {page_size}"
            )
            params = {"source_id": str(source_id)}

        try:
            count_records = await self._execute_read(count_query, **params)
            total = int(count_records[0]["total"]) if count_records else 0

            data_records = await self._execute_read(data_query, **params)
            relationships = [self._record_to_temporal_relationship(r) for r in data_records]

            return relationships, total
        except Exception as e:
            logger.error("Failed to get relationships by source: %s", str(e))
            raise RepositoryError(f"Failed to get relationships by source {source_id}: {e}", e)

    async def get_by_target(
        self,
        target_id: UUID,
        rel_type: Optional[GraphRelationshipType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalRelationship], int]:
        """Get relationships by target node."""
        logger.debug("Getting relationships by target", extra={"target_id": str(target_id)})

        if rel_type:
            count_query = (
                "MATCH ()-[r {rel_type: $rel_type}]->(target {id: $target_id}) "
                "RETURN count(r) AS total"
            )
            data_query = (
                "MATCH (source)-[r {rel_type: $rel_type}]->(target {id: $target_id}) "
                "RETURN r, source "
                f"SKIP {(page - 1) * page_size} LIMIT {page_size}"
            )
            params = {"target_id": str(target_id), "rel_type": rel_type.value}
        else:
            count_query = (
                "MATCH ()-[r]->(target {id: $target_id}) "
                "RETURN count(r) AS total"
            )
            data_query = (
                "MATCH (source)-[r]->(target {id: $target_id}) "
                "RETURN r, source "
                f"SKIP {(page - 1) * page_size} LIMIT {page_size}"
            )
            params = {"target_id": str(target_id)}

        try:
            count_records = await self._execute_read(count_query, **params)
            total = int(count_records[0]["total"]) if count_records else 0

            data_records = await self._execute_read(data_query, **params)
            relationships = [self._record_to_temporal_relationship(r) for r in data_records]

            return relationships, total
        except Exception as e:
            logger.error("Failed to get relationships by target: %s", str(e))
            raise RepositoryError(f"Failed to get relationships by target {target_id}: {e}", e)

    async def get_path(
        self,
        source_id: UUID,
        target_id: UUID,
        max_depth: int = 5,
    ) -> list[list[TemporalRelationship]]:
        """Find paths between two nodes."""
        logger.debug("Finding paths", extra={
            "source_id": str(source_id),
            "target_id": str(target_id),
            "max_depth": max_depth,
        })

        query = (
            "MATCH path = allShortestPaths((source {id: $source_id})-[*..$max_depth]-(target {id: $target_id})) "
            "RETURN [r IN relationships(path) | r {.*}] AS relationships, length(path) AS depth "
            "ORDER BY depth ASC"
        )

        try:
            records = await self._execute_read(
                query,
                source_id=str(source_id),
                target_id=str(target_id),
                max_depth=max_depth,
            )

            paths = []
            for record in records:
                if isinstance(record, dict):
                    rels_data = record.get("relationships", [])
                else:
                    rels_data = record.get("relationships", []) if hasattr(record, "get") else []

                path_rels = []
                for rel_data in rels_data:
                    rel = self._record_to_temporal_relationship(rel_data)
                    path_rels.append(rel)
                paths.append(path_rels)

            return paths
        except Exception as e:
            logger.error("Failed to find paths: %s", str(e))
            raise RepositoryError(f"Failed to find path from {source_id} to {target_id}: {e}", e)

    async def get_temporal_snapshot(
        self,
        rel_id: UUID,
        as_of: datetime,
    ) -> Optional[TemporalRelationship]:
        """Get relationship state at a specific point in time."""
        query = (
            "MATCH ()-[r {id: $id}]-() "
            f"WHERE {build_temporal_filter('r', 'as_of')} "
            "RETURN r LIMIT 1"
        )

        try:
            records = await self._execute_read(query, id=str(rel_id), as_of=as_of.isoformat())
            if not records:
                return None
            return self._record_to_temporal_relationship(records[0])
        except Exception as e:
            logger.error("Failed to get temporal snapshot for relationship: %s", str(e))
            raise RepositoryError(f"Failed to get temporal snapshot for relationship {rel_id}: {e}", e)

    async def soft_delete(self, rel_id: UUID) -> None:
        """Soft-delete a relationship."""
        logger.info("Soft-deleting relationship", extra={"rel_id": str(rel_id)})

        now = datetime.now(timezone.utc).isoformat()
        query = (
            "MATCH ()-[r {id: $id}]-() "
            "WHERE r.valid_to IS NULL "
            "SET r.valid_to = datetime($now) "
            "RETURN r"
        )

        try:
            records = await self._execute_write(query, id=str(rel_id), now=now)
            if not records:
                raise EntityNotFoundError("GraphRelationship", rel_id)
            logger.info("Relationship soft-deleted", extra={"rel_id": str(rel_id)})
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to soft-delete relationship: %s", str(e))
            raise RepositoryError(f"Failed to soft-delete relationship {rel_id}: {e}", e)

    # ------------------------------------------------------------------
    # GraphQueryRepository implementation
    # ------------------------------------------------------------------

    async def traverse(
        self,
        start_id: UUID,
        rel_types: Optional[list[GraphRelationshipType]] = None,
        direction: str = "outgoing",
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """Traverse the graph from a start node."""
        logger.debug("Traversing graph", extra={
            "start_id": str(start_id),
            "direction": direction,
            "max_depth": max_depth,
        })

        type_filter = " | ".join(f":{t.value}" for t in rel_types) if rel_types else ""

        arrow = {"outgoing": "->", "incoming": "<-", "both": "-"}.get(direction, "->")
        rel_pattern = f"[r{type_filter}*1..{max_depth}]" if type_filter else f"[r*1..{max_depth}]"
        full_pattern = f"({arrow}{rel_pattern}{arrow})" if direction == "both" else f"{arrow}{rel_pattern}"

        query = (
            f"MATCH (start {{id: $start_id}}){full_pattern}(neighbor) "
            "RETURN collect(DISTINCT start {.*}) AS start_nodes, "
            "collect(DISTINCT neighbor {.*}) AS neighbor_nodes, "
            "collect(DISTINCT r) AS relationships"
        )

        try:
            records = await self._execute_read(query, start_id=str(start_id))
            if not records:
                return {"nodes": [], "relationships": []}

            record = records[0]
            nodes: list[dict[str, Any]] = []
            relationships: list[dict[str, Any]] = []

            start_nodes_data = record.get("start_nodes", []) if isinstance(record, dict) else []
            neighbor_nodes_data = record.get("neighbor_nodes", []) if isinstance(record, dict) else []
            rels_data = record.get("relationships", []) if isinstance(record, dict) else []

            for n_data in start_nodes_data:
                try:
                    node = self._record_to_temporal_node(n_data)
                    nodes.append(node.to_dict())
                except Exception:
                    pass

            for n_data in neighbor_nodes_data:
                try:
                    node = self._record_to_temporal_node(n_data)
                    nodes.append(node.to_dict())
                except Exception:
                    pass

            for rel_list in rels_data:
                if isinstance(rel_list, list):
                    for r_data in rel_list:
                        try:
                            rel = self._record_to_temporal_relationship(r_data)
                            relationships.append(rel.to_dict())
                        except Exception:
                            pass
                else:
                    try:
                        rel = self._record_to_temporal_relationship(rel_list)
                        relationships.append(rel.to_dict())
                    except Exception:
                        pass

            return {"nodes": nodes, "relationships": relationships}
        except Exception as e:
            logger.error("Graph traversal failed: %s", str(e))
            raise QueryExecutionError(str(e), query, e)

    async def hybrid_search(
        self,
        query_text: str,
        embedding: Optional[list[float]] = None,
        filters: Optional[dict[str, Any]] = None,
        top_k: int = 20,
    ) -> list[NodeWithScore]:
        """Hybrid search combining text and vector similarity."""
        logger.debug("Hybrid search", extra={"query": query_text[:100], "top_k": top_k})

        from regulaforge.knowledge_graph.infrastructure.cypher_queries import HYBRID_SEARCH

        params: dict[str, Any] = {
            "query_text": query_text,
            "embedding": embedding or [],
            "filters": filters,
            "top_k": top_k,
        }

        try:
            records = await self._execute_read(HYBRID_SEARCH, **params)
            results = []
            for record in records:
                if isinstance(record, dict):
                    node_id = record.get("id")
                    score = float(record.get("score", 0.0))

                    node_dict = {
                        "id": node_id,
                        "node_type": record.get("node_type", "REGULATION"),
                        "labels": record.get("labels", []),
                        "title": record.get("title", ""),
                        "code": record.get("code", ""),
                        "embedding": record.get("embedding"),
                    }

                    try:
                        temp_node = self._record_to_temporal_node(node_dict)
                        results.append(NodeWithScore(node=temp_node, score=score))
                    except Exception:
                        pass

            return results
        except Exception as e:
            logger.error("Hybrid search failed: %s", str(e))
            raise QueryExecutionError(str(e), HYBRID_SEARCH, e)

    async def get_neighborhood(
        self,
        node_id: UUID,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Get the subgraph neighborhood around a node."""
        logger.debug("Getting neighborhood", extra={
            "node_id": str(node_id),
            "depth": depth,
        })

        from regulaforge.knowledge_graph.infrastructure.cypher_queries import FIND_NEIGHBORHOOD

        params = {
            "node_id": str(node_id),
            "depth": depth,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

        try:
            records = await self._execute_read(FIND_NEIGHBORHOOD, **params)
            if not records:
                return {"nodes": [], "relationships": []}

            record = records[0]
            nodes: list[dict[str, Any]] = []
            relationships: list[dict[str, Any]] = []

            center_list = record.get("center_nodes", []) if isinstance(record, dict) else []
            neighbor_list = record.get("neighbor_nodes", []) if isinstance(record, dict) else []
            rels = record.get("relationships", []) if isinstance(record, dict) else []

            for n_data in center_list:
                try:
                    node = self._record_to_temporal_node(n_data)
                    nodes.append(node.to_dict())
                except Exception:
                    pass

            for n_data in neighbor_list:
                try:
                    node = self._record_to_temporal_node(n_data)
                    nodes.append(node.to_dict())
                except Exception:
                    pass

            for r_data in rels:
                try:
                    if isinstance(r_data, list):
                        for rd in r_data:
                            rel = self._record_to_temporal_relationship(rd)
                            relationships.append(rel.to_dict())
                    else:
                        rel = self._record_to_temporal_relationship(r_data)
                        relationships.append(rel.to_dict())
                except Exception:
                    pass

            return {"nodes": nodes, "relationships": relationships}
        except Exception as e:
            logger.error("Failed to get neighborhood: %s", str(e))
            raise QueryExecutionError(str(e), FIND_NEIGHBORHOOD, e)

    async def shortest_path(
        self,
        source_id: UUID,
        target_id: UUID,
        _rel_types: Optional[list[GraphRelationshipType]] = None,
    ) -> Optional[dict[str, Any]]:
        """Find shortest path between two nodes."""
        logger.debug("Finding shortest path", extra={
            "source_id": str(source_id),
            "target_id": str(target_id),
        })

        from regulaforge.knowledge_graph.infrastructure.cypher_queries import FIND_PATH

        params: dict[str, Any] = {
            "source_id": str(source_id),
            "target_id": str(target_id),
            "max_depth": 10,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

        try:
            records = await self._execute_read(FIND_PATH, **params)
            if not records:
                return None

            record = records[0]
            return {
                "nodes": record.get("nodes", []) if isinstance(record, dict) else [],
                "relationships": record.get("relationships", []) if isinstance(record, dict) else [],
                "depth": record.get("depth", 0) if isinstance(record, dict) else 0,
            }
        except Exception as e:
            logger.error("Failed to find shortest path: %s", str(e))
            raise QueryExecutionError(str(e), FIND_PATH, e)

    async def query_cypher(
        self,
        cypher_query: str,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Execute a raw Cypher query with optional parameters."""
        logger.debug("Executing raw Cypher query")

        try:
            records = await self._execute_read(cypher_query, **params)
            return [dict(r) for r in records] if records else []
        except QueryExecutionError:
            raise
        except Exception as e:
            logger.error("Raw Cypher query failed: %s", str(e))
            raise QueryExecutionError(str(e), cypher_query, e)

    async def batch_save_nodes(
        self,
        nodes: list[TemporalNode],
        batch_size: int = 100,
    ) -> int:
        """Save multiple nodes in batch.

        Args:
            nodes: List of TemporalNode to save.
            batch_size: Number of nodes per transaction.

        Returns:
            Number of nodes saved.
        """
        saved = 0
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            tasks = [self.save(node) for node in batch]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.error("Batch node save failed: %s", str(result))
                    else:
                        saved += 1
            except Exception as e:
                logger.error("Batch node save error: %s", str(e))
        return saved

    async def batch_save_relationships(
        self,
        relationships: list[TemporalRelationship],
        batch_size: int = 100,
    ) -> int:
        """Save multiple relationships in batch."""
        saved = 0
        for i in range(0, len(relationships), batch_size):
            batch = relationships[i:i + batch_size]
            tasks = [self.save(rel) for rel in batch]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.error("Batch relationship save failed: %s", str(result))
                    else:
                        saved += 1
            except Exception as e:
                logger.error("Batch relationship save error: %s", str(e))
        return saved
