"""Knowledge Graph service — core business logic for graph operations.

This service orchestrates all graph mutation operations including
node creation, relationship linking, temporal versioning, and
external knowledge merging. All methods include validation,
logging, error handling, and event publishing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.config.logging import get_logger
from regulaforge.knowledge_graph.domain.events import (
    GraphMerged,
    NodeCreated,
    NodeTemporalVersionCreated,
    NodeUpdated,
    RelationshipCreated,
)
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
    TemporalRelationship,
)
from regulaforge.knowledge_graph.domain.repository import (
    EntityNotFoundError,
    GraphNodeRepository,
    GraphQueryRepository,
    GraphRelationshipRepository,
)
from regulaforge.knowledge_graph.infrastructure.cypher_queries import (
    FIND_AFFECTED_ENTITIES,
    GET_ENTITY_OBLIGATIONS,
    GET_IMPACT_ANALYSIS,
)
from regulaforge.knowledge_graph.infrastructure.graph_embeddings import (
    GraphEmbeddingService,
)

logger = get_logger(__name__)


class KnowledgeGraphService:
    """Application service for managing the temporal knowledge graph.

    Handles regulation ingestion, clause linking, temporal versioning,
    impact analysis, and external knowledge merging.
    """

    def __init__(
        self,
        node_repo: GraphNodeRepository,
        rel_repo: GraphRelationshipRepository,
        query_repo: GraphQueryRepository,
        embedding_service: GraphEmbeddingService,
        event_publisher: Optional[EventPublisher] = None,
    ) -> None:
        if not node_repo:
            raise ValueError("node_repo is required")
        if not rel_repo:
            raise ValueError("rel_repo is required")
        if not query_repo:
            raise ValueError("query_repo is required")
        if not embedding_service:
            raise ValueError("embedding_service is required")

        self._node_repo = node_repo
        self._rel_repo = rel_repo
        self._query_repo = query_repo
        self._embedding_service = embedding_service
        self._event_publisher = event_publisher

    async def _publish_event(self, event: Any) -> None:
        """Publish a domain event if an event publisher is configured."""
        if self._event_publisher:
            try:
                await self._event_publisher.publish(event)
            except Exception as e:
                logger.error("Failed to publish event %s: %s", event.event_type, str(e))

    async def get_node_by_id(
        self,
        node_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> Optional[TemporalNode]:
        """Get a node by ID, optionally at a point in time."""
        if as_of:
            return await self._node_repo.get_temporal_snapshot(node_id, as_of)
        return await self._node_repo.get_by_id(node_id)

    async def list_nodes_by_type(
        self,
        node_type: GraphNodeType,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        """List nodes by type with pagination."""
        return await self._node_repo.get_by_type(node_type, page=page, page_size=page_size)

    async def list_nodes_by_label(
        self,
        label: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        """List nodes by label with pagination."""
        return await self._node_repo.get_by_label(label, page=page, page_size=page_size)

    async def save_relationship(
        self,
        relationship: TemporalRelationship,
    ) -> TemporalRelationship:
        """Save a relationship to the graph."""
        return await self._rel_repo.save(relationship)

    async def get_relationship_by_id(
        self,
        rel_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> Optional[TemporalRelationship]:
        """Get a relationship by ID, optionally at a point in time."""
        if as_of:
            return await self._rel_repo.get_temporal_snapshot(rel_id, as_of)
        return await self._rel_repo.get_by_id(rel_id)

    async def save_node(self, node: TemporalNode) -> TemporalNode:
        """Persist a node to the graph."""
        return await self._node_repo.save(node)

    async def create_regulation_node(
        self,
        regulation_data: dict[str, Any],
    ) -> TemporalNode:
        """Ingest a regulation into the knowledge graph as a temporal node.

        Args:
            regulation_data: Dictionary containing regulation properties
                (title, code, description, issuing_body, jurisdiction, etc.).

        Returns:
            The created TemporalNode.

        Raises:
            ValueError: If required fields are missing.
            RepositoryError: If persistence fails.
        """
        logger.info("Creating regulation node", extra={"data_keys": list(regulation_data.keys())})

        if "title" not in regulation_data or "code" not in regulation_data:
            raise ValueError("regulation_data must contain 'title' and 'code'")

        node_id = uuid4()
        now = datetime.now(timezone.utc)

        properties = {
            "title": regulation_data["title"],
            "code": regulation_data["code"],
            "description": regulation_data.get("description", ""),
            "issuing_body": regulation_data.get("issuing_body", ""),
            "jurisdiction": regulation_data.get("jurisdiction", ""),
            "category": regulation_data.get("category", ""),
            "status": regulation_data.get("status", "active"),
            "effective_date": str(regulation_data.get("effective_date", "")),
            "version_str": regulation_data.get("version", "1.0"),
            "tags": regulation_data.get("tags", []),
            **{k: v for k, v in regulation_data.items() if k not in (
                "title", "code", "description", "issuing_body",
                "jurisdiction", "category", "status", "effective_date",
                "version", "tags",
            )},
        }

        labels = regulation_data.get("labels", [])
        if "regulation" not in str(labels).lower():
            labels.append("regulation")

        valid_from_str = regulation_data.get("valid_from")
        valid_from = (
            datetime.fromisoformat(valid_from_str) if isinstance(valid_from_str, str) else now
        )

        node = TemporalNode(
            id=node_id,
            node_type=GraphNodeType.REGULATION,
            labels=labels,
            properties=properties,
            valid_from=valid_from,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )

        try:
            node.embedding = await self._embedding_service.generate_node_embedding(node)
        except Exception as e:
            logger.warning("Failed to generate embedding for regulation node %s: %s", node_id, str(e))

        saved = await self._node_repo.save(node)
        await self._publish_event(NodeCreated(
            node_id=saved.id,
            node_type=saved.node_type.value,
            labels=saved.labels,
            properties=saved.properties,
        ))

        logger.info("Created regulation node", extra={"node_id": str(saved.id), "code": regulation_data["code"]})
        return saved

    async def link_regulation_clause(
        self,
        regulation_id: UUID,
        clause_data: dict[str, Any],
    ) -> TemporalRelationship:
        """Link a clause node to a regulation with a DERIVES_FROM relationship.

        Args:
            regulation_id: The UUID of the regulation node.
            clause_data: Dictionary containing clause properties.

        Returns:
            The created TemporalRelationship.

        Raises:
            EntityNotFoundError: If the regulation node is not found.
            ValueError: If clause_data is invalid.
        """
        logger.info("Linking clause to regulation", extra={"regulation_id": str(regulation_id)})

        regulation = await self._node_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("GraphNode", regulation_id)

        now = datetime.now(timezone.utc)
        clause_id = uuid4()

        clause_node = TemporalNode(
            id=clause_id,
            node_type=GraphNodeType.CLAUSE,
            labels=clause_data.get("labels", ["clause"]),
            properties={
                "clause_id": clause_data.get("clause_id", ""),
                "title": clause_data.get("title", ""),
                "text": clause_data.get("text", ""),
                "section": clause_data.get("section", ""),
                "obligation_summary": clause_data.get("obligation_summary", ""),
                **{k: v for k, v in clause_data.items() if k not in (
                    "clause_id", "title", "text", "section", "obligation_summary", "labels",
                )},
            },
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )

        try:
            clause_node.embedding = await self._embedding_service.generate_node_embedding(clause_node)
        except Exception as e:
            logger.warning("Failed to generate embedding for clause node %s: %s", clause_id, str(e))

        saved_clause = await self._node_repo.save(clause_node)
        await self._publish_event(NodeCreated(
            node_id=saved_clause.id,
            node_type=saved_clause.node_type.value,
            labels=saved_clause.labels,
            properties=saved_clause.properties,
        ))

        relationship = TemporalRelationship(
            id=uuid4(),
            source_id=regulation_id,
            target_id=clause_id,
            rel_type=GraphRelationshipType.DERIVES_FROM,
            properties={
                "context": clause_data.get("context", ""),
                "mapped_at": now.isoformat(),
            },
            valid_from=now,
            valid_to=None,
            version=1,
            created_at=now,
            updated_at=now,
        )

        saved_rel = await self._rel_repo.save(relationship)
        await self._publish_event(RelationshipCreated(
            relationship_id=saved_rel.id,
            source_id=saved_rel.source_id,
            target_id=saved_rel.target_id,
            rel_type=saved_rel.rel_type.value,
            properties=saved_rel.properties,
        ))

        logger.info("Linked clause to regulation", extra={
            "regulation_id": str(regulation_id),
            "clause_id": str(clause_id),
            "rel_id": str(saved_rel.id),
        })
        return saved_rel

    async def update_node_properties(
        self,
        node_id: UUID,
        properties: dict[str, Any],
        valid_from: Optional[datetime] = None,
    ) -> TemporalNode:
        """Update a node's properties, creating a new temporal version.

        The current version is closed (valid_to set) and a new version
        is created with the updated properties.

        Args:
            node_id: The UUID of the node to update.
            properties: Dictionary of properties to update.
            valid_from: When this version becomes valid (defaults to now).

        Returns:
            The new temporal version of the node.

        Raises:
            EntityNotFoundError: If the node is not found.
        """
        logger.info("Updating node properties", extra={"node_id": str(node_id)})

        current = await self._node_repo.get_by_id(node_id)
        if not current:
            raise EntityNotFoundError("GraphNode", node_id)

        now = datetime.now(timezone.utc)
        effective_from = valid_from or now

        if effective_from <= current.valid_from:
            raise ValueError("valid_from must be after the current version's valid_from")

        current.valid_to = effective_from
        current.updated_at = now
        await self._node_repo.save(current)

        new_properties = dict(current.properties)
        changed = {}
        for key, value in properties.items():
            if key in new_properties and new_properties[key] != value:  # noqa: SIM114
                changed[key] = value
            elif key not in new_properties:
                changed[key] = value
            new_properties[key] = value

        new_version = TemporalNode(
            id=current.id,
            node_type=current.node_type,
            labels=list(current.labels),
            properties=new_properties,
            valid_from=effective_from,
            valid_to=None,
            version=current.version + 1,
            created_at=current.created_at,
            updated_at=now,
            embedding=current.embedding,
        )

        try:
            new_version.embedding = await self._embedding_service.generate_node_embedding(new_version)
        except Exception as e:
            logger.warning("Failed to regenerate embedding for node %s: %s", node_id, str(e))

        saved = await self._node_repo.save(new_version)
        await self._publish_event(NodeUpdated(
            node_id=saved.id,
            node_type=saved.node_type.value,
            changed_properties=changed,
            new_version=saved.version,
        ))
        await self._publish_event(NodeTemporalVersionCreated(
            node_id=saved.id,
            node_type=saved.node_type.value,
            version=saved.version,
            valid_from=saved.valid_from.isoformat(),
            valid_to=saved.valid_to.isoformat() if saved.valid_to else None,
        ))

        logger.info("Updated node properties", extra={
            "node_id": str(node_id),
            "new_version": saved.version,
            "changed_properties": list(changed.keys()),
        })
        return saved

    async def get_regulation_impact(
        self,
        regulation_id: UUID,
    ) -> dict[str, Any]:
        """Analyze the full impact of a regulation on entities and obligations.

        Args:
            regulation_id: The UUID of the regulation node.

        Returns:
            Dictionary with impacted entities, obligations, and affected clauses.

        Raises:
            EntityNotFoundError: If the regulation is not found.
        """
        logger.info("Getting regulation impact", extra={"regulation_id": str(regulation_id)})

        regulation = await self._node_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("GraphNode", regulation_id)

        try:
            impact_records = await self._query_repo.query_cypher(
                GET_IMPACT_ANALYSIS,
                regulation_id=str(regulation_id),
            )
            impact = impact_records[0] if impact_records else {}
        except Exception as e:
            logger.error("Failed to get impact analysis: %s", str(e))
            impact = {}

        result: dict[str, Any] = {
            "regulation_id": str(regulation_id),
            "regulation_title": regulation.properties.get("title", ""),
            "regulation_code": regulation.properties.get("code", ""),
            "impacted_entities": impact.get("entities", []),
            "obligations": impact.get("obligations", []),
            "affected_clauses": impact.get("clauses", []),
            "risk_factors": impact.get("risk_factors", []),
        }

        logger.info("Regulation impact retrieved", extra={
            "regulation_id": str(regulation_id),
            "entity_count": len(result["impacted_entities"]),
            "obligation_count": len(result["obligations"]),
        })
        return result

    async def find_affected_entities(
        self,
        regulation_id: UUID,
    ) -> list[dict[str, Any]]:
        """Find all entities that need to comply with a given regulation.

        Args:
            regulation_id: The UUID of the regulation node.

        Returns:
            List of entity dictionaries with compliance context.

        Raises:
            EntityNotFoundError: If the regulation is not found.
        """
        logger.info("Finding affected entities", extra={"regulation_id": str(regulation_id)})

        regulation = await self._node_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("GraphNode", regulation_id)

        try:
            entities_result = await self._query_repo.query_cypher(
                FIND_AFFECTED_ENTITIES,
                regulation_id=str(regulation_id),
            )
        except Exception as e:
            logger.error("Failed to find affected entities: %s", str(e))
            entities_result = []

        entities = list(entities_result) if isinstance(entities_result, list) else []
        logger.info("Found affected entities", extra={
            "regulation_id": str(regulation_id),
            "count": len(entities),
        })
        return entities

    async def get_temporal_evolution(
        self,
        regulation_code: str,
    ) -> dict[str, Any]:
        """Get the full amendment history and temporal evolution of a regulation.

        Args:
            regulation_code: The regulation code (e.g., 'RBI-MASTER-2024').

        Returns:
            Dictionary with version history and amendment chain.
        """
        logger.info("Getting temporal evolution", extra={"regulation_code": regulation_code})

        try:
            nodes_result, _ = await self._node_repo.get_by_label(
                label=regulation_code,
                page=1,
                page_size=100,
            )
        except Exception as e:
            logger.error("Failed to get temporal evolution: %s", str(e))
            return {
                "regulation_code": regulation_code,
                "versions": [],
                "amendments": [],
                "error": str(e),
            }

        versions = [n.to_dict() for n in nodes_result]

        amendment_rels = []
        for version in nodes_result:
            try:
                rels, _ = await self._rel_repo.get_by_source(
                    source_id=UUID(version.id) if isinstance(version.id, str) else version.id,
                    rel_type=GraphRelationshipType.AMENDS,
                    page=1,
                    page_size=50,
                )
                amendment_rels.extend(r.to_dict() for r in rels)
            except Exception:
                pass

        result: dict[str, Any] = {
            "regulation_code": regulation_code,
            "versions": sorted(versions, key=lambda v: v["version"]),
            "amendments": amendment_rels,
            "version_count": len(versions),
            "amendment_count": len(amendment_rels),
        }

        logger.info("Temporal evolution retrieved", extra={
            "regulation_code": regulation_code,
            "version_count": result["version_count"],
        })
        return result

    async def merge_external_knowledge(
        self,
        source_type: str,
        source_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge external knowledge (regulations, obligations) into the graph.

        Supports bulk import from regulatory databases, document parsers,
        or API integrations.

        Args:
            source_type: Identifier for the source (e.g., 'rbi_api', 'document_parser').
            source_data: Dictionary containing nodes and relationships to merge.

        Returns:
            Dictionary with merge statistics (nodes_created, relationships_created, errors).

        Raises:
            ValueError: If source_data is malformed.
        """
        logger.info("Merging external knowledge", extra={"source_type": source_type})

        if not source_data or not isinstance(source_data, dict):
            raise ValueError("source_data must be a non-empty dictionary")

        nodes_data = source_data.get("nodes", [])
        relationships_data = source_data.get("relationships", [])

        if not isinstance(nodes_data, list):
            raise ValueError("source_data.nodes must be a list")
        if not isinstance(relationships_data, list):
            raise ValueError("source_data.relationships must be a list")

        nodes_created = 0
        rels_created = 0
        errors: list[str] = []

        for node_data in nodes_data:
            try:
                node_type_str = node_data.get("node_type", "REGULATION")
                try:
                    node_type = GraphNodeType(node_type_str)
                except ValueError:
                    node_type = GraphNodeType.REGULATION

                now = datetime.now(timezone.utc)

                node = TemporalNode(
                    id=UUID(node_data.get("id", str(uuid4()))),
                    node_type=node_type,
                    labels=node_data.get("labels", []),
                    properties=node_data.get("properties", {}),
                    valid_from=datetime.fromisoformat(node_data["valid_from"]) if "valid_from" in node_data else now,
                    valid_to=datetime.fromisoformat(node_data["valid_to"]) if node_data.get("valid_to") else None,
                    version=node_data.get("version", 1),
                )

                try:
                    node.embedding = await self._embedding_service.generate_node_embedding(node)
                except Exception as e:
                    logger.warning("Embedding generation failed for merged node: %s", str(e))

                await self._node_repo.save(node)
                nodes_created += 1
            except Exception as e:
                error_msg = f"Failed to merge node: {e!s}"
                errors.append(error_msg)
                logger.error(error_msg)

        for rel_data in relationships_data:
            try:
                rel_type_str = rel_data.get("rel_type", "REFERENCES")
                try:
                    rel_type = GraphRelationshipType(rel_type_str)
                except ValueError:
                    rel_type = GraphRelationshipType.REFERENCES

                now = datetime.now(timezone.utc)

                relationship = TemporalRelationship(
                    id=UUID(rel_data.get("id", str(uuid4()))),
                    source_id=UUID(rel_data["source_id"]),
                    target_id=UUID(rel_data["target_id"]),
                    rel_type=rel_type,
                    properties=rel_data.get("properties", {}),
                    valid_from=datetime.fromisoformat(rel_data["valid_from"]) if "valid_from" in rel_data else now,
                    valid_to=datetime.fromisoformat(rel_data["valid_to"]) if rel_data.get("valid_to") else None,
                )

                await self._rel_repo.save(relationship)
                rels_created += 1
            except Exception as e:
                error_msg = f"Failed to merge relationship: {e!s}"
                errors.append(error_msg)
                logger.error(error_msg)

        stats: dict[str, Any] = {
            "source_type": source_type,
            "nodes_created": nodes_created,
            "relationships_created": rels_created,
            "errors": errors,
            "error_count": len(errors),
        }

        await self._publish_event(GraphMerged(
            source_type=source_type,
            nodes_created=nodes_created,
            relationships_created=rels_created,
        ))

        logger.info("External knowledge merged", extra=stats)
        return stats

    async def compare_versions(
        self,
        node_id: UUID,
        version_a: int,
        version_b: int,
    ) -> dict[str, Any]:
        """Compare two versions of a node and return the property diff.

        Args:
            node_id: UUID of the node.
            version_a: First version number.
            version_b: Second version number.

        Returns:
            Dictionary with version_a, version_b data and the diff.

        Raises:
            EntityNotFoundError: If the node or either version is not found.
        """
        logger.info(
            "Comparing versions",
            extra={"node_id": str(node_id), "version_a": version_a, "version_b": version_b},
        )

        node = await self._node_repo.get_by_id(node_id)
        if not node:
            raise EntityNotFoundError("GraphNode", node_id)

        history = await self._node_repo.get_temporal_history(node_id)
        versions = {v.version: v for v in history}
        va = versions.get(version_a)
        vb = versions.get(version_b)

        if not va:
            raise ValueError(f"Version {version_a} not found for node {node_id}")
        if not vb:
            raise ValueError(f"Version {version_b} not found for node {node_id}")

        props_a = va.properties
        props_b = vb.properties
        keys_a = set(props_a.keys())
        keys_b = set(props_b.keys())

        added = {k: props_b[k] for k in keys_b - keys_a}
        removed = {k: props_a[k] for k in keys_a - keys_b}
        changed = {
            k: {"from": props_a[k], "to": props_b[k]}
            for k in keys_a & keys_b
            if props_a[k] != props_b[k]
        }

        return {
            "node_id": str(node_id),
            "version_a": version_a,
            "version_b": version_b,
            "node_at_version_a": va.to_dict(),
            "node_at_version_b": vb.to_dict(),
            "diff": {
                "added": added,
                "removed": removed,
                "changed": changed,
                "change_count": len(added) + len(removed) + len(changed),
            },
        }

    async def get_compliance_obligations(
        self,
        entity_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Get all compliance obligations for an entity at a point in time.

        Queries regulations that APPLY_TO the entity, then finds obligations
        CREATES_OBLIGATION from those regulations.

        Args:
            entity_id: The UUID of the entity node.
            as_of: The point in time to query (defaults to now).

        Returns:
            List of obligation dictionaries with regulation context.

        Raises:
            EntityNotFoundError: If the entity is not found.
        """
        as_of = as_of or datetime.now(timezone.utc)
        logger.info("Getting compliance obligations", extra={
            "entity_id": str(entity_id),
            "as_of": as_of.isoformat(),
        })

        entity = await self._node_repo.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError("GraphNode", entity_id)

        try:
            obligations_result = await self._query_repo.query_cypher(
                GET_ENTITY_OBLIGATIONS,
                entity_id=str(entity_id),
            )
        except Exception as e:
            logger.error("Failed to get compliance obligations: %s", str(e))
            obligations_result = []

        obligations = list(obligations_result) if isinstance(obligations_result, list) else []
        flattened = []
        for entry in obligations:
            reg_obligations = entry.get("obligations", []) if isinstance(entry, dict) else []
            if isinstance(reg_obligations, list):
                flattened.extend(reg_obligations)

        logger.info("Compliance obligations retrieved", extra={
            "entity_id": str(entity_id),
            "count": len(flattened),
        })
        return flattened
