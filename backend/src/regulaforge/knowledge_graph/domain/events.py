"""Domain events for the Temporal Knowledge Graph.

Each event captures a meaningful state change in the graph,
enabling event-driven communication with other bounded contexts.
"""

from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class NodeCreated(DomainEvent):
    """A new node was created in the knowledge graph."""

    def __init__(
        self,
        node_id: UUID,
        node_type: str,
        labels: list[str],
        properties: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.node.created",
            aggregate_id=node_id,
            aggregate_type="graph_node",
            data={
                "node_id": str(node_id),
                "node_type": node_type,
                "labels": labels,
                "properties": {k: str(v) for k, v in properties.items()},
            },
            correlation_id=correlation_id,
        )


class NodeUpdated(DomainEvent):
    """An existing node's properties were updated."""

    def __init__(
        self,
        node_id: UUID,
        node_type: str,
        changed_properties: dict[str, Any],
        new_version: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.node.updated",
            aggregate_id=node_id,
            aggregate_type="graph_node",
            data={
                "node_id": str(node_id),
                "node_type": node_type,
                "changed_properties": {k: str(v) for k, v in changed_properties.items()},
                "new_version": new_version,
            },
            correlation_id=correlation_id,
        )


class NodeArchived(DomainEvent):
    """A node was soft-deleted / archived in the knowledge graph."""

    def __init__(
        self,
        node_id: UUID,
        node_type: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.node.archived",
            aggregate_id=node_id,
            aggregate_type="graph_node",
            data={
                "node_id": str(node_id),
                "node_type": node_type,
            },
            correlation_id=correlation_id,
        )


class NodeTemporalVersionCreated(DomainEvent):
    """A new temporal version was created for an existing node."""

    def __init__(
        self,
        node_id: UUID,
        node_type: str,
        version: int,
        valid_from: str,
        valid_to: Optional[str],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.node.temporal_version_created",
            aggregate_id=node_id,
            aggregate_type="graph_node",
            data={
                "node_id": str(node_id),
                "node_type": node_type,
                "version": version,
                "valid_from": valid_from,
                "valid_to": valid_to,
            },
            correlation_id=correlation_id,
        )


class RelationshipCreated(DomainEvent):
    """A new relationship was created between two nodes."""

    def __init__(
        self,
        relationship_id: UUID,
        source_id: UUID,
        target_id: UUID,
        rel_type: str,
        properties: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.relationship.created",
            aggregate_id=relationship_id,
            aggregate_type="graph_relationship",
            data={
                "relationship_id": str(relationship_id),
                "source_id": str(source_id),
                "target_id": str(target_id),
                "rel_type": rel_type,
                "properties": {k: str(v) for k, v in properties.items()},
            },
            correlation_id=correlation_id,
        )


class RelationshipUpdated(DomainEvent):
    """An existing relationship was updated."""

    def __init__(
        self,
        relationship_id: UUID,
        rel_type: str,
        changed_properties: dict[str, Any],
        new_version: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.relationship.updated",
            aggregate_id=relationship_id,
            aggregate_type="graph_relationship",
            data={
                "relationship_id": str(relationship_id),
                "rel_type": rel_type,
                "changed_properties": {k: str(v) for k, v in changed_properties.items()},
                "new_version": new_version,
            },
            correlation_id=correlation_id,
        )


class RelationshipDeleted(DomainEvent):
    """A relationship was deleted (soft-delete) from the knowledge graph."""

    def __init__(
        self,
        relationship_id: UUID,
        source_id: UUID,
        target_id: UUID,
        rel_type: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.relationship.deleted",
            aggregate_id=relationship_id,
            aggregate_type="graph_relationship",
            data={
                "relationship_id": str(relationship_id),
                "source_id": str(source_id),
                "target_id": str(target_id),
                "rel_type": rel_type,
            },
            correlation_id=correlation_id,
        )


class GraphMerged(DomainEvent):
    """External knowledge was merged into the knowledge graph."""

    def __init__(
        self,
        source_type: str,
        nodes_created: int,
        relationships_created: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            event_type="knowledge_graph.graph.merged",
            aggregate_id=UUID(int=0),
            aggregate_type="knowledge_graph",
            data={
                "source_type": source_type,
                "nodes_created": nodes_created,
                "relationships_created": relationships_created,
            },
            correlation_id=correlation_id,
        )
