"""Bridge between the Temporal Knowledge Graph and GraphRAG engine.

Translates knowledge_graph domain data (regulations, clauses, obligations,
entities) into GraphRAG-compatible format (Document, Chunk, Entity nodes)
for unified graph-powered retrieval and generation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.knowledge_graph.application.graph_query_service import GraphQueryService
from regulaforge.knowledge_graph.application.graph_service import KnowledgeGraphService
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    TemporalNode,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeGraphGraphRAGBridge:
    """Coordinates between the Knowledge Graph and GraphRAG subsystems.

    Provides bidirectional translation:
      knowledge_graph → graphrag: export KG nodes as Document/Chunk/Entity
      graphrag → knowledge_graph: enrich KG with GraphRAG retrieval signals
    """

    def __init__(
        self,
        kg_service: KnowledgeGraphService,
        kg_query_service: GraphQueryService,
        graphrag_neo4j: Any,  # graphrag Neo4jClient duck-type
    ) -> None:
        if not kg_service:
            raise ValueError("kg_service is required")
        if not kg_query_service:
            raise ValueError("kg_query_service is required")
        if not graphrag_neo4j:
            raise ValueError("graphrag_neo4j client is required")

        self._kg_service = kg_service
        self._kg_query = kg_query_service
        self._graphrag_neo4j = graphrag_neo4j

    # ------------------------------------------------------------------
    # Knowledge Graph → GraphRAG export
    # ------------------------------------------------------------------

    async def export_regulation_as_document(
        self,
        regulation_id: UUID,
    ) -> dict[str, Any]:
        """Export a regulation node and its neighborhood as a GraphRAG Document.

        Creates a Document node, chunks the regulation text, extracts entities,
        and links everything in the GraphRAG Neo4j schema.

        Returns a summary dict with document_id, chunks, entities.
        """
        node = await self._kg_service.get_node_by_id(regulation_id)
        if not node:
            raise ValueError(f"Regulation {regulation_id} not found")

        title = node.properties.get("title", "Untitled")
        code = node.properties.get("code", str(regulation_id))
        text = self._build_document_text(node)

        doc_id = str(uuid4())
        await self._graphrag_neo4j.create_document_node(
            type("Doc", (), {
                "id": doc_id,
                "title": title,
                "source": f"knowledge_graph:{code}",
                "doc_type": "REGULATION",
                "jurisdiction": node.properties.get("jurisdiction", ""),
                "regulatory_body": node.properties.get("issuing_body", ""),
                "published_date": node.properties.get("effective_date") or None,
                "metadata": {
                    "kg_node_id": str(regulation_id),
                    "kg_node_type": node.node_type.value,
                    "kg_version": node.version,
                },
                "created_at": _now(),
            })(),
        )

        chunks = self._chunk_regulation_text(text, doc_id, title)
        chunk_ids: list[str] = []
        for chunk in chunks:
            await self._graphrag_neo4j.create_chunk_node(chunk)
            await self._graphrag_neo4j.link_chunk_to_document(chunk.id, doc_id)
            chunk_ids.append(chunk.id)

        entities = self._extract_entities_from_node(node, doc_id)
        entity_ids: list[str] = []
        for entity in entities:
            await self._graphrag_neo4j.create_entity_node(entity)
            entity_ids.append(entity["id"])

        for chunk_id in chunk_ids:
            for ent in entities:
                await self._graphrag_neo4j.link_entity_to_chunk(
                    ent["id"], chunk_id, confidence=0.8,
                )

        logger.info(
            "Exported regulation %s as GraphRAG document %s: %d chunks, %d entities",
            code, doc_id, len(chunks), len(entities),
        )

        return {
            "document_id": doc_id,
            "kg_node_id": str(regulation_id),
            "regulation_code": code,
            "title": title,
            "chunks": len(chunks),
            "entities": len(entities),
        }

    async def sync_all_regulations(self) -> list[dict[str, Any]]:
        """Export all regulation nodes in the knowledge graph to GraphRAG.

        Returns a list of export summaries.
        """
        nodes, total = await self._kg_service.list_nodes_by_type(
            GraphNodeType.REGULATION,
        )
        results: list[dict[str, Any]] = []
        for node in nodes:
            try:
                summary = await self.export_regulation_as_document(node.id)
                results.append(summary)
            except Exception as e:
                logger.warning("Failed to export regulation %s: %s", node.id, e)
                results.append({
                    "kg_node_id": str(node.id),
                    "error": str(e),
                })
        logger.info("Synced %d/%d regulations to GraphRAG", len(results), total)
        return results

    # ------------------------------------------------------------------
    # GraphRAG → Knowledge Graph enrichment
    # ------------------------------------------------------------------

    async def enrich_node_with_graphrag_context(
        self,
        node_id: UUID,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Enrich a KG node with context retrieved from GraphRAG.

        Uses the node's title and properties as a query against the
        GraphRAG hybrid retriever to find related documents and chunks.

        Returns the original node data plus the graphrag context.
        """
        node = await self._kg_service.get_node_by_id(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")

        query_text = node.properties.get("title", "")
        code = node.properties.get("code", "")
        if code:
            query_text = f"{query_text} {code}"

        try:
            context = await self._graphrag_neo4j.query_graph(
                type("GQ", (), {
                    "node_labels": None,
                    "relationship_types": None,
                    "entity_names": [query_text],
                    "entity_categories": None,
                    "max_depth": 2,
                    "min_confidence": 0.0,
                    "limit": top_k,
                })(),
            )
        except Exception as e:
            logger.warning("GraphRAG query failed for node %s: %s", node_id, e)
            context = []

        return {
            "node_id": str(node_id),
            "node_type": node.node_type.value,
            "title": node.properties.get("title"),
            "graphrag_paths": [
                {
                    "length": p.length if hasattr(p, "length") else 0,
                    "node_count": len(p.nodes) if hasattr(p, "nodes") else 0,
                }
                for p in (context or [])
            ],
            "graphrag_path_count": len(context or []),
        }

    # ------------------------------------------------------------------
    # Combined search
    # ------------------------------------------------------------------

    async def search_across_systems(
        self,
        query_text: str,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """Search both knowledge_graph and GraphRAG for comprehensive results.

        Returns:
            Dict with 'kg_results' (from hybrid_search) and
            'graphrag_results' (from GraphRAG retrieval).
        """
        kg_results = await self._kg_query.hybrid_search(
            query_text=query_text,
            top_k=top_k,
        )

        graphrag_results: list[dict[str, Any]] = []
        try:
            paths = await self._graphrag_neo4j.query_graph(
                type("GQ", (), {
                    "node_labels": None,
                    "relationship_types": None,
                    "entity_names": [query_text],
                    "entity_categories": None,
                    "max_depth": 2,
                    "min_confidence": 0.0,
                    "limit": top_k,
                })(),
            )
            for path in paths or []:
                graphrag_results.append({
                    "length": path.length if hasattr(path, "length") else 0,
                    "score": path.score if hasattr(path, "score") else 0,
                    "node_count": len(path.nodes) if hasattr(path, "nodes") else 0,
                })
        except Exception as e:
            logger.warning("GraphRAG search failed: %s", e)

        return {
            "query": query_text,
            "kg_results": kg_results,
            "kg_result_count": len(kg_results),
            "graphrag_results": graphrag_results,
            "graphrag_result_count": len(graphrag_results),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_document_text(self, node: TemporalNode) -> str:
        """Build a plain-text representation of a KG node for document indexing."""
        parts: list[str] = []
        props = node.properties

        title = props.get("title", "")
        if title:
            parts.append(f"# {title}")

        code = props.get("code", "")
        if code:
            parts.append(f"Code: {code}")

        desc = props.get("description", "")
        if desc:
            parts.append(f"\n{desc}")

        for key, value in props.items():
            if key in ("title", "code", "description", "tags", "version_str"):
                continue
            if value:
                parts.append(f"{key}: {value}")

        tags = props.get("tags", [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        return "\n\n".join(parts)

    def _chunk_regulation_text(
        self,
        text: str,
        document_id: str,
        title: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ) -> list[Any]:
        """Split regulation text into chunks for GraphRAG indexing."""
        chunks: list[Any] = []
        import re

        paragraphs = re.split(r"\n\s*\n", text)
        current_chunk: list[str] = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_len = len(para.split())

            if current_length + para_len > chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(
                    type("Chunk", (), {
                        "id": str(uuid4()),
                        "document_id": document_id,
                        "text": chunk_text,
                        "chunk_index": len(chunks),
                        "embedding": [],
                        "metadata": {"source": "knowledge_graph"},
                        "page_number": None,
                        "heading": title[:200] if len(chunks) == 0 else "",
                    })(),
                )
                overlap_text = current_chunk[-1] if current_chunk else ""
                overlap_words = overlap_text.split()
                if len(overlap_words) > chunk_overlap:
                    current_chunk = [" ".join(overlap_words[-chunk_overlap:])]
                    current_length = len(overlap_words[-chunk_overlap:])
                else:
                    current_chunk = [overlap_text]
                    current_length = len(overlap_words)
                current_chunk.append(para)
                current_length += para_len
            else:
                current_chunk.append(para)
                current_length += para_len

        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                type("Chunk", (), {
                    "id": str(uuid4()),
                    "document_id": document_id,
                    "text": chunk_text,
                    "chunk_index": len(chunks),
                    "embedding": [],
                    "metadata": {"source": "knowledge_graph"},
                    "page_number": None,
                    "heading": "",
                })(),
            )

        return chunks

    def _extract_entities_from_node(
        self,
        node: TemporalNode,
        document_id: str,
    ) -> list[Any]:
        """Extract GraphRAG-style entities from a KG node's properties."""
        entities: list[Any] = []
        props = node.properties

        entity_catalog = {
            "issuing_body": ("ORGANIZATION", props.get("issuing_body")),
            "jurisdiction": ("JURISDICTION", props.get("jurisdiction")),
            "category": ("REGULATION", props.get("category")),
        }

        for key, (category, value) in entity_catalog.items():
            if value:
                entities.append(
                    type("Ent", (), {
                        "id": str(uuid4()),
                        "name": str(value),
                        "category": category,
                        "aliases": [],
                        "description": f"Extracted from KG node {node.id} ({key})",
                        "embedding": [],
                        "metadata": {
                            "kg_node_id": str(node.id),
                            "kg_source": key,
                        },
                        "first_seen": _now(),
                        "last_seen": _now(),
                    })(),
                )

        return entities
