"""Interface layer for the Temporal Knowledge Graph.

Contains FastAPI routes that expose knowledge graph operations
as RESTful endpoints. No business logic — only request parsing,
delegation to application services, and response formatting.

Import the router directly:
    from regulaforge.knowledge_graph.interfaces.api import router
"""

__all__ = ["router"]
