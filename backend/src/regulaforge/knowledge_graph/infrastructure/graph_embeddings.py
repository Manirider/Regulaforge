"""Graph embedding service — generates vector embeddings for graph nodes.

Uses the LLMProvider port to generate embeddings for nodes and queries,
enabling semantic search and similarity matching in the knowledge graph.
"""

from __future__ import annotations

from typing import Any, Optional

from regulaforge.application.ports.llm_provider import LLMProvider, LLMProviderError
from regulaforge.config.logging import get_logger
from regulaforge.knowledge_graph.domain.models import TemporalNode

logger = get_logger(__name__)


class GraphEmbeddingService:
    """Generates vector embeddings for knowledge graph nodes and queries.

    Uses the configured LLM provider to create embeddings that enable
    semantic search, similarity matching, and GraphRAG capabilities.
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self._llm_provider = llm_provider

    async def generate_node_embedding(self, node: TemporalNode) -> list[float]:
        """Generate an embedding vector for a graph node.

        Constructs a text representation of the node using its type,
        labels, and key properties, then embeds it via the LLM provider.

        Args:
            node: The TemporalNode to embed.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            LLMProviderError: If the embedding provider is unavailable.
        """
        if not self._llm_provider:
            logger.warning("No LLM provider configured — returning empty embedding")
            return []

        text = self._construct_node_text(node)

        try:
            embedding = await self._llm_provider.embed(text)
            logger.debug(
                "Generated embedding for node",
                extra={
                    "node_id": str(node.id),
                    "node_type": node.node_type.value,
                    "embedding_dim": len(embedding),
                },
            )
            return embedding
        except LLMProviderError as e:
            logger.error(
                "Failed to generate embedding for node %s: %s",
                str(node.id), str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error generating embedding for node %s: %s",
                str(node.id), str(e),
            )
            return []

    async def generate_query_embedding(self, query_text: str) -> list[float]:
        """Generate an embedding vector for a search query.

        Args:
            query_text: The query text to embed.

        Returns:
            A list of floats representing the query embedding vector.

        Raises:
            LLMProviderError: If the embedding provider is unavailable.
        """
        if not self._llm_provider:
            logger.warning("No LLM provider configured — returning empty query embedding")
            return []

        if not query_text or not query_text.strip():
            logger.warning("Empty query text provided for embedding")
            return []

        try:
            embedding = await self._llm_provider.embed(query_text)
            logger.debug(
                "Generated query embedding",
                extra={
                    "query_length": len(query_text),
                    "embedding_dim": len(embedding),
                },
            )
            return embedding
        except LLMProviderError as e:
            logger.error("Failed to generate query embedding: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error generating query embedding: %s", str(e))
            return []

    async def update_all_node_embeddings(
        self,
        nodes: list[TemporalNode],
    ) -> dict[str, Any]:
        """Regenerate embeddings for a batch of nodes.

        Args:
            nodes: List of TemporalNode objects to re-embed.

        Returns:
            Dictionary with update statistics (total, updated, failed).
        """
        if not self._llm_provider:
            logger.warning("No LLM provider configured — skipping batch embedding update")
            return {"total": len(nodes), "updated": 0, "failed": len(nodes)}

        logger.info("Updating embeddings for %d nodes", len(nodes))

        updated = 0
        failed = 0

        for node in nodes:
            try:
                embedding = await self.generate_node_embedding(node)
                if embedding:
                    node.embedding = embedding
                    updated += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(
                    "Failed to update embedding for node %s: %s",
                    str(node.id), str(e),
                )
                failed += 1

        stats: dict[str, Any] = {
            "total": len(nodes),
            "updated": updated,
            "failed": failed,
        }

        logger.info("Batch embedding update completed", extra=stats)
        return stats

    @staticmethod
    def _construct_node_text(node: TemporalNode) -> str:
        """Construct a text representation of a node suitable for embedding.

        Combines type, labels, title, description, and key properties
        into a single text string that captures the node's semantic meaning.

        Args:
            node: The TemporalNode to convert to text.

        Returns:
            A text string representing the node.
        """
        parts: list[str] = []
        parts.append(f"Node Type: {node.node_type.value}")

        if node.labels:
            parts.append(f"Labels: {', '.join(node.labels)}")

        props = node.properties

        title = props.get("title") or props.get("name")
        if title:
            parts.append(f"Title: {title}")

        code = props.get("code")
        if code:
            parts.append(f"Code: {code}")

        description = props.get("description") or props.get("text")
        if description:
            parts.append(f"Description: {description[:500]}")

        issuing_body = props.get("issuing_body")
        if issuing_body:
            parts.append(f"Issuing Body: {issuing_body}")

        jurisdiction = props.get("jurisdiction")
        if jurisdiction:
            parts.append(f"Jurisdiction: {jurisdiction}")

        category = props.get("category")
        if category:
            parts.append(f"Category: {category}")

        tags = props.get("tags")
        if tags and isinstance(tags, list):
            parts.append(f"Tags: {', '.join(str(t) for t in tags)}")

        clause_id = props.get("clause_id")
        if clause_id:
            parts.append(f"Clause: {clause_id}")

        section = props.get("section")
        if section:
            parts.append(f"Section: {section}")

        obligation_summary = props.get("obligation_summary")
        if obligation_summary:
            parts.append(f"Obligation: {obligation_summary[:300]}")

        additional = {k: v for k, v in props.items() if k not in (
            "title", "name", "code", "description", "text",
            "issuing_body", "jurisdiction", "category", "tags",
            "clause_id", "section", "obligation_summary",
            "status", "effective_date", "version_str",
        )}
        if additional:
            extras = ", ".join(f"{k}: {v}" for k, v in list(additional.items())[:5])
            if extras:
                parts.append(f"Additional: {extras}")

        return " | ".join(parts)
