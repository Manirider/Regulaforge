"""Graph Query service — advanced queries against the temporal knowledge graph.

Provides hybrid search, regulation chain traversal, coverage analysis,
overlap detection, impact analysis, and natural-language-driven semantic
queries. All methods include validation, logging, and error handling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from regulaforge.config.logging import get_logger
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
)
from regulaforge.knowledge_graph.domain.repository import (
    EntityNotFoundError,
    GraphNodeRepository,
    GraphQueryRepository,
    GraphRelationshipRepository,
)
from regulaforge.knowledge_graph.infrastructure.graph_embeddings import (
    GraphEmbeddingService,
)

logger = get_logger(__name__)


class GraphQueryService:
    """Application service for advanced knowledge graph queries.

    Provides semantic search, traversal, coverage analysis, overlap detection,
    and impact analysis capabilities on top of the temporal knowledge graph.
    """

    def __init__(
        self,
        node_repo: GraphNodeRepository,
        rel_repo: GraphRelationshipRepository,
        query_repo: GraphQueryRepository,
        embedding_service: GraphEmbeddingService,
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

    async def hybrid_search(
        self,
        query_text: str,
        embedding: Optional[list[float]] = None,
        filters: Optional[dict[str, Any]] = None,
        top_k: int = 20,
        as_of: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Perform hybrid (text + vector) search with temporal filtering.

        Args:
            query_text: The natural language query text.
            embedding: Optional pre-computed embedding vector.
            filters: Optional filters (node_type, labels, etc.).
            top_k: Maximum number of results (default 20).
            as_of: Temporal filter — only return nodes valid at this time.

        Returns:
            Ranked list of nodes with explanations and relevance scores.

        Raises:
            ValueError: If query_text is empty.
        """
        if not query_text or not query_text.strip():
            raise ValueError("query_text must be a non-empty string")

        logger.info("Hybrid search", extra={
            "query": query_text[:100],
            "top_k": top_k,
            "has_filters": filters is not None,
        })

        if embedding is None:
            try:
                embedding = await self._embedding_service.generate_query_embedding(query_text)
            except Exception as e:
                logger.warning("Failed to generate query embedding, falling back to text-only: %s", str(e))

        try:
            results = await self._query_repo.hybrid_search(
                query_text=query_text,
                embedding=embedding,
                filters=filters,
                top_k=top_k,
            )
        except Exception as e:
            logger.error("Hybrid search failed: %s", str(e))
            return []

        ranked: list[dict[str, Any]] = []
        for item in results:
            node = item.node if hasattr(item, "node") else item
            score = item.score if hasattr(item, "score") else 0.0

            if as_of and hasattr(node, "valid_from"):
                if node.valid_from > as_of:
                    continue
                if hasattr(node, "valid_to") and node.valid_to and node.valid_to <= as_of:
                    continue

            explanation = self._build_search_explanation(node, score, query_text)

            ranked.append({
                "node": node.to_dict() if hasattr(node, "to_dict") else node,
                "score": score,
                "explanation": explanation,
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        logger.info("Hybrid search completed", extra={"result_count": len(ranked)})
        return ranked

    async def traverse_regulation_chain(
        self,
        regulation_id: UUID,
        direction: str = "outgoing",
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """Traverse the regulation dependency chain (AMENDS, SUPERSEDES, DERIVES_FROM).

        Args:
            regulation_id: Starting regulation node UUID.
            direction: 'outgoing', 'incoming', or 'both'.
            max_depth: Maximum traversal depth.

        Returns:
            Dictionary with the dependency chain subgraph.

        Raises:
            EntityNotFoundError: If the regulation is not found.
        """
        logger.info("Traversing regulation chain", extra={
            "regulation_id": str(regulation_id),
            "direction": direction,
            "max_depth": max_depth,
        })

        node = await self._node_repo.get_by_id(regulation_id)
        if not node:
            raise EntityNotFoundError("GraphNode", regulation_id)

        try:
            subgraph = await self._query_repo.traverse(
                start_id=regulation_id,
                rel_types=[
                    GraphRelationshipType.AMENDS,
                    GraphRelationshipType.SUPERSEDES,
                    GraphRelationshipType.DERIVES_FROM,
                    GraphRelationshipType.REFERENCES,
                    GraphRelationshipType.REPLACES,
                ],
                direction=direction,
                max_depth=max_depth,
            )
        except Exception as e:
            logger.error("Regulation chain traversal failed: %s", str(e))
            return {
                "regulation_id": str(regulation_id),
                "nodes": [],
                "relationships": [],
                "error": str(e),
            }

        result: dict[str, Any] = {
            "regulation_id": str(regulation_id),
            "regulation_code": node.properties.get("code", ""),
            "regulation_title": node.properties.get("title", ""),
            "nodes": subgraph.get("nodes", []),
            "relationships": subgraph.get("relationships", []),
            "node_count": len(subgraph.get("nodes", [])),
            "relationship_count": len(subgraph.get("relationships", [])),
        }

        logger.info("Regulation chain traversal completed", extra={
            "node_count": result["node_count"],
            "rel_count": result["relationship_count"],
        })
        return result

    async def get_regulation_coverage(
        self,
        entity_type: str,
        jurisdiction: str,
    ) -> dict[str, Any]:
        """Get a coverage map of regulations applicable to a given entity type and jurisdiction.

        Args:
            entity_type: The type of entity (e.g., 'bank', 'insurer', 'fintech').
            jurisdiction: The jurisdiction (e.g., 'RBI', 'SEBI', 'IRDAI').

        Returns:
            Dictionary with regulation coverage breakdown by category.
        """
        logger.info("Getting regulation coverage", extra={
            "entity_type": entity_type,
            "jurisdiction": jurisdiction,
        })

        try:
            regulations, total = await self._node_repo.get_by_type(
                node_type=GraphNodeType.REGULATION,
                page=1,
                page_size=1000,
            )
        except Exception as e:
            logger.error("Failed to get regulations for coverage: %s", str(e))
            return {
                "entity_type": entity_type,
                "jurisdiction": jurisdiction,
                "total_regulations": 0,
                "coverage_by_category": {},
                "error": str(e),
            }

        filtered: list[dict[str, Any]] = []
        for reg in regulations:
            props = reg.properties
            reg_jurisdiction = props.get("jurisdiction", "").lower()
            if (
                jurisdiction.lower() == "global"
                or reg_jurisdiction == jurisdiction.lower()
                or reg_jurisdiction == "global"
            ):
                filtered.append(props)

        coverage: dict[str, int] = {}
        for props in filtered:
            category = props.get("category", "uncategorized")
            coverage[category] = coverage.get(category, 0) + 1

        result: dict[str, Any] = {
            "entity_type": entity_type,
            "jurisdiction": jurisdiction,
            "total_regulations": len(filtered),
            "coverage_by_category": coverage,
            "categories": sorted(coverage.items()),
        }

        logger.info("Regulation coverage retrieved", extra={
            "total": result["total_regulations"],
            "categories": len(coverage),
        })
        return result

    async def find_overlapping_obligations(
        self,
        entity_id: UUID,
        regulations: Optional[list[UUID]] = None,
    ) -> list[dict[str, Any]]:
        """Find duplicate or near-duplicate obligations for an entity across regulations.

        Args:
            entity_id: The UUID of the entity to analyze.
            regulations: Optional list of regulation UUIDs to scope the analysis.

        Returns:
            List of overlapping obligation groups with similarity scores.

        Raises:
            EntityNotFoundError: If the entity is not found.
        """
        logger.info("Finding overlapping obligations", extra={"entity_id": str(entity_id)})

        entity = await self._node_repo.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError("GraphNode", entity_id)

        if regulations:
            obligations: list[dict[str, Any]] = []
            for reg_id in regulations:
                try:
                    rels, _ = await self._rel_repo.get_by_source(
                        source_id=reg_id,
                        rel_type=GraphRelationshipType.CREATES_OBLIGATION,
                        page=1,
                        page_size=500,
                    )
                    for rel in rels:
                        target = await self._node_repo.get_by_id(rel.target_id)
                        if target:
                            obligations.append(target.to_dict())
                except Exception:
                    continue
        else:
            try:
                rels, _ = await self._rel_repo.get_by_target(
                    target_id=entity_id,
                    page=1,
                    page_size=500,
                )
                obligations = []
                for rel in rels:
                    source = await self._node_repo.get_by_id(rel.source_id)
                    if source and source.node_type == GraphNodeType.OBLIGATION:
                        obligations.append(source.to_dict())
            except Exception as e:
                logger.error("Failed to find overlapping obligations: %s", str(e))
                return []

        overlaps: list[dict[str, Any]] = []
        seen_texts: dict[str, list[dict[str, Any]]] = {}
        for obl in obligations:
            text = obl.get("properties", {}).get("text", "") or obl.get("properties", {}).get("title", "")
            key = text[:100].lower().strip()
            if key not in seen_texts:
                seen_texts[key] = []
            seen_texts[key].append(obl)

        for key, group in seen_texts.items():
            if len(group) > 1:
                overlaps.append({
                    "similar_text": key,
                    "obligations": group,
                    "count": len(group),
                    "score": 1.0 - (len(key) / max(len(k) for k in seen_texts)) if seen_texts else 0.0,
                })

        overlaps.sort(key=lambda x: x["count"], reverse=True)
        logger.info("Overlapping obligations found", extra={
            "entity_id": str(entity_id),
            "overlap_groups": len(overlaps),
        })
        return overlaps

    async def get_impact_analysis(
        self,
        regulation_code: str,
    ) -> dict[str, Any]:
        """Generate a comprehensive impact analysis report for a regulation.

        Args:
            regulation_code: The regulation code (e.g., 'RBI-MASTER-2024').

        Returns:
            Dictionary with the full impact analysis report.
        """
        logger.info("Getting impact analysis", extra={"regulation_code": regulation_code})

        regulation = await self._find_regulation_by_code(regulation_code)
        if not regulation:
            return {
                "regulation_code": regulation_code,
                "error": "Regulation not found in knowledge graph",
            }

        regulation_id = UUID(regulation.id) if isinstance(regulation.id, str) else regulation.id

        try:
            impact = await self.get_regulation_impact(regulation_id)
        except Exception:
            impact = {"impacted_entities": [], "obligations": [], "affected_clauses": []}

        try:
            evolution = await self.get_temporal_evolution(regulation_code)
        except Exception:
            evolution = {"versions": [], "amendments": []}

        try:
            affected = await self.find_affected_entities(regulation_id)
        except Exception:
            affected = []

        report: dict[str, Any] = {
            "regulation_code": regulation_code,
            "regulation_title": regulation.properties.get("title", ""),
            "jurisdiction": regulation.properties.get("jurisdiction", ""),
            "category": regulation.properties.get("category", ""),
            "status": regulation.properties.get("status", ""),
            "effective_date": regulation.properties.get("effective_date", ""),
            "impacted_entities": impact.get("impacted_entities", []),
            "obligations": impact.get("obligations", []),
            "affected_clauses": impact.get("affected_clauses", []),
            "affected_entities": affected,
            "amendment_history": evolution.get("amendments", []),
            "version_history": evolution.get("versions", []),
            "entity_count": len(impact.get("impacted_entities", [])) + len(affected),
            "obligation_count": len(impact.get("obligations", [])),
            "version_count": len(evolution.get("versions", [])),
        }

        logger.info("Impact analysis completed", extra={
            "regulation_code": regulation_code,
            "entity_count": report["entity_count"],
            "obligation_count": report["obligation_count"],
        })
        return report

    async def semantic_query(
        self,
        natural_language_query: str,
    ) -> dict[str, Any]:
        """Convert a natural language query into a graph query and execute it.

        Args:
            natural_language_query: A query in plain English
                (e.g., 'Show me all RBI regulations from 2024 with compliance obligations').

        Returns:
            Dictionary with the interpreted query, executed results, and explanation.

        Raises:
            ValueError: If the query is empty.
        """
        if not natural_language_query or not natural_language_query.strip():
            raise ValueError("natural_language_query must be a non-empty string")

        logger.info("Semantic query", extra={"query": natural_language_query[:100]})

        nlq_lower = natural_language_query.lower()

        filters: dict[str, Any] = {}
        query_type = "search"

        jurisdiction_map = {
            "rbi": "RBI", "sebi": "SEBI", "irdai": "IRDAI",
            "reserve bank": "RBI", "securities": "SEBI", "insurance": "IRDAI",
        }
        for keyword, jurs in jurisdiction_map.items():
            if keyword in nlq_lower:
                filters["jurisdiction"] = jurs
                break

        category_map = {
            "aml": "anti_money_laundering", "kyc": "know_your_customer",
            "data protection": "data_protection", "privacy": "privacy",
            "cyber": "cybersecurity", "corporate governance": "corporate_governance",
        }
        for keyword, cat in category_map.items():
            if keyword in nlq_lower:
                filters["category"] = cat
                break

        year_filters = [w for w in nlq_lower.split() if w.isdigit() and len(w) == 4]
        if year_filters:
            filters["year"] = year_filters[0]

        if "obligation" in nlq_lower or "compliance" in nlq_lower:
            filters["has_obligations"] = True

        if "impact" in nlq_lower or "affected" in nlq_lower:
            query_type = "impact"

        if "evolution" in nlq_lower or "history" in nlq_lower or "amendment" in nlq_lower:
            query_type = "evolution"

        if "coverage" in nlq_lower or "map" in nlq_lower:
            query_type = "coverage"

        if "overlap" in nlq_lower or "duplicate" in nlq_lower or "near-duplicate" in nlq_lower:
            query_type = "overlap"

        try:
            embedding = await self._embedding_service.generate_query_embedding(natural_language_query)
        except Exception as e:
            logger.warning("Failed to generate embedding for semantic query: %s", str(e))
            embedding = None

        try:
            search_results = await self.hybrid_search(
                query_text=natural_language_query,
                embedding=embedding,
                filters=filters if filters else None,
                top_k=10,
            )
        except Exception as e:
            logger.error("Semantic query search failed: %s", str(e))
            search_results = []

        result: dict[str, Any] = {
            "natural_language_query": natural_language_query,
            "interpretation": {
                "query_type": query_type,
                "filters_applied": filters,
                "has_semantic_search": embedding is not None,
            },
            "results": search_results,
            "result_count": len(search_results),
        }

        logger.info("Semantic query completed", extra={
            "query_type": query_type,
            "result_count": result["result_count"],
        })
        return result

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
        logger.info("Getting regulation impact (via query service)", extra={"regulation_id": str(regulation_id)})

        regulation = await self._node_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("GraphNode", regulation_id)

        try:
            neighborhood = await self._query_repo.get_neighborhood(
                node_id=regulation_id,
                depth=3,
            )
        except Exception as e:
            logger.error("Failed to get regulation neighborhood: %s", str(e))
            neighborhood = {"nodes": [], "relationships": []}

        entities: list[dict[str, Any]] = []
        obligations: list[dict[str, Any]] = []
        clauses: list[dict[str, Any]] = []

        for node_data in neighborhood.get("nodes", []):
            node = node_data if isinstance(node_data, dict) else node_data.to_dict()
            node_type = node.get("node_type", "") if isinstance(node, dict) else node.node_type.value
            if node_type == GraphNodeType.ENTITY.value:
                entities.append(node)
            elif node_type == GraphNodeType.OBLIGATION.value:
                obligations.append(node)
            elif node_type == GraphNodeType.CLAUSE.value:
                clauses.append(node)

        return {
            "regulation_id": str(regulation_id),
            "regulation_code": regulation.properties.get("code", ""),
            "regulation_title": regulation.properties.get("title", ""),
            "impacted_entities": entities,
            "obligations": obligations,
            "affected_clauses": clauses,
            "risk_factors": [],
        }

    async def get_temporal_evolution(
        self,
        regulation_code: str,
    ) -> dict[str, Any]:
        """Get the full amendment history and temporal evolution of a regulation.

        Args:
            regulation_code: The regulation code.

        Returns:
            Dictionary with version history and amendment chain.
        """
        logger.info("Getting temporal evolution (via query service)", extra={"regulation_code": regulation_code})

        regulation = await self._find_regulation_by_code(regulation_code)
        if not regulation:
            return {"regulation_code": regulation_code, "versions": [], "amendments": [], "version_count": 0, "amendment_count": 0}

        reg_id = UUID(regulation.id) if isinstance(regulation.id, str) else regulation.id

        try:
            version_nodes = await self._node_repo.get_temporal_history(reg_id)
        except Exception as e:
            logger.error("Failed to get temporal evolution: %s", str(e))
            return {"regulation_code": regulation_code, "versions": [], "amendments": []}

        versions = [n.to_dict() for n in version_nodes]
        amendment_rels = []

        for version_node in version_nodes:
            try:
                rels, _ = await self._rel_repo.get_by_source(
                    source_id=UUID(version_node.id) if isinstance(version_node.id, str) else version_node.id,
                    rel_type=GraphRelationshipType.AMENDS,
                    page=1,
                    page_size=50,
                )
                amendment_rels.extend(r.to_dict() for r in rels)
            except Exception:
                pass

        return {
            "regulation_code": regulation_code,
            "versions": sorted(versions, key=lambda v: v["version"]),
            "amendments": amendment_rels,
            "version_count": len(versions),
            "amendment_count": len(amendment_rels),
        }

    async def find_affected_entities(
        self,
        regulation_id: UUID,
    ) -> list[dict[str, Any]]:
        """Find all entities affected by a regulation.

        Args:
            regulation_id: The UUID of the regulation node.

        Returns:
            List of affected entity dictionaries.

        Raises:
            EntityNotFoundError: If the regulation is not found.
        """
        logger.info("Finding affected entities (via query service)", extra={"regulation_id": str(regulation_id)})

        regulation = await self._node_repo.get_by_id(regulation_id)
        if not regulation:
            raise EntityNotFoundError("GraphNode", regulation_id)

        try:
            rels, _ = await self._rel_repo.get_by_source(
                source_id=regulation_id,
                rel_type=GraphRelationshipType.APPLIES_TO,
                page=1,
                page_size=500,
            )
        except Exception as e:
            logger.error("Failed to find affected entities: %s", str(e))
            return []

        entities = []
        for rel in rels:
            try:
                entity = await self._node_repo.get_by_id(rel.target_id)
                if entity and entity.node_type == GraphNodeType.ENTITY:
                    entities.append(entity.to_dict())
            except Exception:
                continue

        return entities

    async def _find_regulation_by_code(self, code: str) -> Optional[TemporalNode]:
        try:
            nodes, _ = await self._node_repo.get_by_type(
                GraphNodeType.REGULATION,
                page=1,
                page_size=1000,
            )
        except Exception:
            return None
        for node in nodes:
            if node.properties.get("code") == code:
                return node
        return None

    def _build_search_explanation(
        self,
        node: Any,
        score: float,
        query: str,
    ) -> str:
        """Build a human-readable explanation of why a node matched a query."""
        node_dict = node.to_dict() if hasattr(node, "to_dict") else node
        props = node_dict.get("properties", {}) if isinstance(node_dict, dict) else {}
        node_type = node_dict.get("node_type", "") if isinstance(node_dict, dict) else ""

        title = props.get("title", props.get("name", "unknown"))
        code = props.get("code", "")

        if score > 0.9:
            relevance = "highly relevant"
        elif score > 0.7:
            relevance = "relevant"
        elif score > 0.4:
            relevance = "somewhat relevant"
        else:
            relevance = "weakly relevant"

        parts = [f"{node_type} '{title}'"]
        if code:
            parts.append(f"({code})")
        parts.append(f"is {relevance} to the query")
        if query:
            parts.append(f"'{query[:50]}'")
        parts.append(f"with similarity score {score:.4f}")

        return " ".join(parts)
