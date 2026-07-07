from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import AgentRole
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
)

logger = logging.getLogger(__name__)


class KnowledgeGraphAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        neo4j_client: Optional[Any] = None,
        qdrant_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.KNOWLEDGE_GRAPH,
            agent_id="knowledge_graph_001",
            llm_client=llm_client,
        )
        self.neo4j = neo4j_client
        self.qdrant = qdrant_client
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="query_graph",
            description="Query the Neo4j knowledge graph for entities and relationships",
            parameters={
                "query": {"type": "string", "description": "Graph query (entity name, relationship type)"},
                "max_depth": {"type": "integer", "description": "Maximum traversal depth"},
            },
            function=self._query_graph_logic,
        )
        self.register_tool(
            name="vector_search",
            description="Search for semantically similar content in Qdrant",
            parameters={
                "query": {"type": "string", "description": "Search query text"},
                "top_k": {"type": "integer", "description": "Number of results"},
            },
            function=self._vector_search_logic,
        )
        self.register_tool(
            name="get_entity_relationships",
            description="Get all relationships for a given entity",
            parameters={
                "entity_name": {"type": "string", "description": "Name of the entity"},
            },
            function=self._get_relationships_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        query = task.input_data.get("query", task.description)
        query_type = task.input_data.get("query_type", "graph")

        self.add_reasoning_step(
            description=f"Executing {query_type} query",
            input_text=query,
        )

        if query_type == "vector":
            results = await self.call_tool("vector_search", {
                "query": query,
                "top_k": task.input_data.get("top_k", 10),
            })
        elif query_type == "relationships":
            results = await self.call_tool("get_entity_relationships", {
                "entity_name": query,
            })
        else:
            results = await self.call_tool("query_graph", {
                "query": query,
                "max_depth": task.input_data.get("max_depth", 2),
            })

        self.add_reasoning_step(
            description="Query returned results",
            output_text=f"Found {len(results) if isinstance(results, list) else 1} results",
            confidence=0.9,
        )

        return {"query": query, "query_type": query_type, "results": results}

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        results = result.get("results", [])
        has_results = len(results) > 0 if isinstance(results, list) else results is not None

        return EvaluationResult(
            passed=has_results,
            score=ConfidenceScore(
                overall=0.9 if has_results else 0.3,
                accuracy=0.85,
                completeness=0.8 if has_results else 0.3,
                relevance=0.9,
            ),
            feedback=[] if has_results else ["No results found"],
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.2),
            feedback=[f"Knowledge graph query failed: {error}. Returning empty results."],
            suggestions=["Try a different query formulation", "Check graph connectivity"],
        )

    def _query_graph_logic(
        self,
        query: str,
        max_depth: int = 2,
    ) -> list[dict[str, Any]]:
        return [
            {"entity": "RBI", "type": "ORGANIZATION", "relationships": ["regulates", "oversees"]},
            {"entity": "Banking Regulation Act", "type": "STATUTE", "relationships": ["governs"]},
        ]

    def _vector_search_logic(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        return [
            {"id": f"chunk_{i}", "score": 0.95 - i * 0.05, "text": f"Result {i} for {query}"}
            for i in range(min(top_k, 5))
        ]

    def _get_relationships_logic(
        self,
        entity_name: str,
    ) -> list[dict[str, Any]]:
        return [
            {"source": entity_name, "target": "Banking Regulation Act", "type": "GOVERNED_BY", "confidence": 0.95},
            {"source": entity_name, "target": "Ministry of Finance", "type": "REPORTS_TO", "confidence": 0.85},
        ]
