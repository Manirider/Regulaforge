"""Repository port interfaces for the Temporal Knowledge Graph.

These are abstract base classes (ports) that define the contract
for data access operations. Infrastructure adapters implement
these interfaces using Neo4j or other graph databases.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
    TemporalRelationship,
)


@dataclass
class NodeWithScore:
    """A graph node paired with a similarity score from vector search."""

    node: TemporalNode
    score: float


class GraphNodeRepository(ABC):
    """Port interface for graph node persistence and retrieval."""

    @abstractmethod
    async def save(self, node: TemporalNode) -> TemporalNode:
        """Persist a new or updated node.

        Args:
            node: The node to persist.

        Returns:
            The persisted node with any generated fields populated.

        Raises:
            RepositoryError: If persistence fails.
        """
        ...

    @abstractmethod
    async def get_by_id(self, node_id: UUID) -> Optional[TemporalNode]:
        """Retrieve a node by its unique identifier.

        Args:
            node_id: The node UUID.

        Returns:
            The node if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_by_type(
        self,
        node_type: GraphNodeType,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        """Retrieve nodes filtered by type with pagination.

        Args:
            node_type: The type of nodes to retrieve.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (nodes list, total count).
        """
        ...

    @abstractmethod
    async def get_by_label(
        self,
        label: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalNode], int]:
        """Retrieve nodes by label with pagination.

        Args:
            label: The label to filter by.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (nodes list, total count).
        """
        ...

    @abstractmethod
    async def search_embedding(
        self,
        embedding: list[float],
        limit: int = 20,
    ) -> list[NodeWithScore]:
        """Search nodes by embedding vector similarity.

        Args:
            embedding: The query embedding vector.
            limit: Maximum number of results.

        Returns:
            List of nodes with their similarity scores.
        """
        ...

    @abstractmethod
    async def get_temporal_snapshot(
        self,
        node_id: UUID,
        as_of: datetime,
    ) -> Optional[TemporalNode]:
        """Retrieve the state of a node as it was at a given point in time.

        Args:
            node_id: The node UUID.
            as_of: The point in time to query.

        Returns:
            The node state at the given time, or None if not found.
        """
        ...

    @abstractmethod
    async def get_temporal_history(
        self,
        node_id: UUID,
    ) -> list[TemporalNode]:
        """Retrieve all historical versions of a node.

        Args:
            node_id: The node UUID.

        Returns:
            List of node versions ordered by valid_from ascending.
        """
        ...

    @abstractmethod
    async def soft_delete(self, node_id: UUID) -> None:
        """Soft-delete a node by setting its valid_to to now.

        Args:
            node_id: The node UUID to soft-delete.

        Raises:
            RepositoryError: If the node is not found or deletion fails.
        """
        ...


class GraphRelationshipRepository(ABC):
    """Port interface for graph relationship persistence and retrieval."""

    @abstractmethod
    async def save(self, relationship: TemporalRelationship) -> TemporalRelationship:
        """Persist a new or updated relationship.

        Args:
            relationship: The relationship to persist.

        Returns:
            The persisted relationship with any generated fields populated.

        Raises:
            RepositoryError: If persistence fails.
        """
        ...

    @abstractmethod
    async def get_by_id(self, rel_id: UUID) -> Optional[TemporalRelationship]:
        """Retrieve a relationship by its unique identifier.

        Args:
            rel_id: The relationship UUID.

        Returns:
            The relationship if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_by_source(
        self,
        source_id: UUID,
        rel_type: Optional[GraphRelationshipType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalRelationship], int]:
        """Retrieve relationships by source node with optional type filter.

        Args:
            source_id: The source node UUID.
            rel_type: Optional relationship type filter.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (relationships list, total count).
        """
        ...

    @abstractmethod
    async def get_by_target(
        self,
        target_id: UUID,
        rel_type: Optional[GraphRelationshipType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TemporalRelationship], int]:
        """Retrieve relationships by target node with optional type filter.

        Args:
            target_id: The target node UUID.
            rel_type: Optional relationship type filter.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (relationships list, total count).
        """
        ...

    @abstractmethod
    async def get_path(
        self,
        source_id: UUID,
        target_id: UUID,
        max_depth: int = 5,
    ) -> list[list[TemporalRelationship]]:
        """Find all paths between two nodes up to a maximum depth.

        Args:
            source_id: The source node UUID.
            target_id: The target node UUID.
            max_depth: Maximum path depth.

        Returns:
            List of paths, where each path is a list of relationships.
        """
        ...

    @abstractmethod
    async def get_temporal_snapshot(
        self,
        rel_id: UUID,
        as_of: datetime,
    ) -> Optional[TemporalRelationship]:
        """Retrieve the state of a relationship as it was at a given point in time.

        Args:
            rel_id: The relationship UUID.
            as_of: The point in time to query.

        Returns:
            The relationship state at the given time, or None.
        """
        ...

    @abstractmethod
    async def soft_delete(self, rel_id: UUID) -> None:
        """Soft-delete a relationship by setting its valid_to to now.

        Args:
            rel_id: The relationship UUID to soft-delete.

        Raises:
            RepositoryError: If the relationship is not found or deletion fails.
        """
        ...


class GraphQueryRepository(ABC):
    """Port interface for advanced graph traversal and query operations."""

    @abstractmethod
    async def traverse(
        self,
        start_id: UUID,
        rel_types: Optional[list[GraphRelationshipType]] = None,
        direction: str = "outgoing",
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """Traverse the graph from a starting node.

        Args:
            start_id: The starting node UUID.
            rel_types: Optional list of relationship types to follow.
            direction: 'outgoing', 'incoming', or 'both'.
            max_depth: Maximum traversal depth.

        Returns:
            A dictionary containing the subgraph of nodes and relationships.
        """
        ...

    @abstractmethod
    async def hybrid_search(
        self,
        query_text: str,
        embedding: Optional[list[float]] = None,
        filters: Optional[dict[str, Any]] = None,
        top_k: int = 20,
    ) -> list[NodeWithScore]:
        """Perform hybrid (text + vector) search against graph nodes.

        Args:
            query_text: The text query for full-text search.
            embedding: Optional embedding vector for semantic search.
            filters: Optional filters to narrow results.
            top_k: Maximum number of results.

        Returns:
            List of nodes with their relevance scores.
        """
        ...

    @abstractmethod
    async def get_neighborhood(
        self,
        node_id: UUID,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Get the subgraph neighborhood around a node.

        Args:
            node_id: The center node UUID.
            depth: The radius of the neighborhood.

        Returns:
            A dictionary containing the subgraph of nodes and relationships.
        """
        ...

    @abstractmethod
    async def shortest_path(
        self,
        source_id: UUID,
        target_id: UUID,
        rel_types: Optional[list[GraphRelationshipType]] = None,
    ) -> Optional[dict[str, Any]]:
        """Find the shortest path between two nodes.

        Args:
            source_id: The source node UUID.
            target_id: The target node UUID.
            rel_types: Optional list of relationship types to traverse.

        Returns:
            A dictionary with the path details, or None if no path exists.
        """
        ...

    @abstractmethod
    async def query_cypher(
        self,
        cypher_query: str,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Execute a raw Cypher query against the graph.

        Args:
            cypher_query: The Cypher query string with parameters.
            **params: Named parameters for the Cypher query.

        Returns:
            List of result records as dictionaries.

        Raises:
            QueryExecutionError: If the query fails.
        """
        ...


from regulaforge.common.exceptions import RepositoryError as _BaseRepositoryError


class RepositoryError(_BaseRepositoryError):
    """Base exception for graph repository operations."""

    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        self.original_error = original_error
        super().__init__(message, code="GRAPH_REPOSITORY_ERROR", status_code=500)


class EntityNotFoundError(RepositoryError):
    """Raised when a graph entity is not found."""

    def __init__(self, entity_type: str, entity_id: UUID) -> None:
        super().__init__(f"{entity_type} with id '{entity_id}' not found")
        self.entity_type = entity_type
        self.entity_id = entity_id


class QueryExecutionError(RepositoryError):
    """Raised when a graph query fails to execute."""

    def __init__(self, message: str, query: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(f"Query execution failed: {message}", original_error)
        self.query = query


class ConnectionError(RepositoryError):
    """Raised when unable to connect to the graph database."""

    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(f"Graph database connection failed: {message}", original_error)
