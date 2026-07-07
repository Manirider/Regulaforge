"""Infrastructure layer for the Temporal Knowledge Graph.

Contains Neo4j adapter, Cypher queries, and embedding service
implementations. Adapts external systems to the domain ports.

Adapters should be imported directly from their modules:
    from regulaforge.knowledge_graph.infrastructure.neo4j_adapter import Neo4jAdapter
"""

__all__ = [
    "Neo4jAdapter",
    "GraphEmbeddingService",
    "CREATE_REGULATION_NODE",
    "CREATE_CLAUSE_NODE",
    "CREATE_OBLIGATION_NODE",
    "CREATE_RELATIONSHIP",
    "FIND_PATH",
    "FIND_NEIGHBORHOOD",
    "HYBRID_SEARCH",
    "GET_TEMPORAL_SNAPSHOT",
    "GET_TEMPORAL_HISTORY",
    "GET_IMPACT_ANALYSIS",
    "FIND_AFFECTED_ENTITIES",
    "MERGE_NODE",
    "MERGE_RELATIONSHIP",
]
