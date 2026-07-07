"""Entity Resolution service for deduplication and merge in the knowledge graph.

Uses fuzzy matching (SequenceMatcher) on node titles, codes, and text
to identify potential duplicates, then applies deterministic merge rules
based on node type, source priority, and temporal ordering.

Scalability: uses blocking-by-first-character to reduce pairwise comparisons
from O(n²) to O(b²) where b is the block size.
"""

from __future__ import annotations

import difflib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.config.logging import get_logger
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    TemporalNode,
)
from regulaforge.knowledge_graph.domain.repository import (
    EntityNotFoundError,
    GraphNodeRepository,
    GraphRelationshipRepository,
)

logger = get_logger(__name__)

SIMILARITY_THRESHOLD_DEFAULT: float = 0.85
MAX_DUPLICATE_SCAN_NODES: int = 5000

_WEIGHT_MAP: dict[str, float] = {
    "title": 0.4,
    "code": 0.3,
    "text": 0.2,
    "name": 0.1,
}


@dataclass
class ResolutionCandidate:
    """A pair of nodes that may represent the same real-world entity."""

    source: TemporalNode
    target: TemporalNode
    similarity_score: float = 0.0
    match_fields: list[str] = field(default_factory=list)


@dataclass
class MergeResult:
    """Result of a merge operation between two nodes."""

    surviving_node_id: UUID
    merged_node_id: UUID
    merged_properties: dict[str, Any]
    merged_labels: list[str]
    conflict_count: int
    merged_relationship_count: int


class EntityResolutionService:
    """Resolves duplicate or near-duplicate graph entities via fuzzy matching."""

    def __init__(
        self,
        node_repo: GraphNodeRepository,
        rel_repo: GraphRelationshipRepository,
        threshold: float = SIMILARITY_THRESHOLD_DEFAULT,
    ) -> None:
        if not node_repo:
            raise ValueError("node_repo is required")
        if not rel_repo:
            raise ValueError("rel_repo is required")
        self._node_repo = node_repo
        self._rel_repo = rel_repo
        self._threshold = threshold

    async def find_duplicates(
        self,
        node_type: Optional[GraphNodeType] = None,
        page_size: int = 500,
    ) -> list[ResolutionCandidate]:
        """Scan graph for potential duplicate nodes using fuzzy matching.

        Uses blocking-by-first-character to reduce pairwise comparisons.
        Loads nodes in batches and groups them by node type + first character
        of title/code before computing similarity within each block.

        Args:
            node_type: Optional type filter (scans all types if None).
            page_size: Batch size for paginated node retrieval.

        Returns:
            List of candidate pairs with similarity scores above threshold.
        """
        logger.info(
            "Scanning for duplicate nodes",
            extra={"node_type": node_type.value if node_type else "ALL", "threshold": self._threshold},
        )

        types_to_scan: list[GraphNodeType] = (
            [node_type] if node_type else list(GraphNodeType)
        )

        all_nodes: list[TemporalNode] = []
        for ntype in types_to_scan:
            try:
                nodes, _ = await self._node_repo.get_by_type(
                    node_type=ntype, page=1, page_size=page_size,
                )
                all_nodes.extend(nodes)
            except Exception as e:
                logger.warning("Failed to fetch nodes for type %s: %s", ntype.value, str(e))

        if len(all_nodes) > MAX_DUPLICATE_SCAN_NODES:
            logger.warning(
                "Duplicate scan truncated: %d nodes exceeds max %d",
                len(all_nodes), MAX_DUPLICATE_SCAN_NODES,
            )
            all_nodes = all_nodes[:MAX_DUPLICATE_SCAN_NODES]

        blocks: dict[str, list[TemporalNode]] = defaultdict(list)
        for node in all_nodes:
            key = self._blocking_key(node)
            blocks[key].append(node)

        candidates: list[ResolutionCandidate] = []
        seen: set[tuple[UUID, UUID]] = set()

        for block_id, block_nodes in blocks.items():
            if len(block_nodes) < 2:
                continue
            for i in range(len(block_nodes)):
                for j in range(i + 1, len(block_nodes)):
                    a, b = block_nodes[i], block_nodes[j]
                    pair = (a.id, b.id)
                    if pair in seen or (b.id, a.id) in seen:
                        continue
                    seen.add(pair)

                    score, fields = self._compute_similarity(a, b)
                    if score >= self._threshold:
                        candidates.append(
                            ResolutionCandidate(
                                source=a, target=b,
                                similarity_score=score,
                                match_fields=fields,
                            )
                        )
                    if len(seen) > MAX_DUPLICATE_SCAN_NODES * 10:
                        break
                if len(seen) > MAX_DUPLICATE_SCAN_NODES * 10:
                    break

        candidates.sort(key=lambda c: c.similarity_score, reverse=True)
        logger.info("Found %d duplicate candidates across %d blocks", len(candidates), len(blocks))
        return candidates

    async def merge_nodes(
        self,
        source_id: UUID,
        target_id: UUID,
        source_priority: bool = True,
    ) -> MergeResult:
        """Merge two nodes into one, preserving the higher-priority node.

        The surviving node absorbs all properties, labels, and relationships
        of the merged node. The merged node is soft-deleted.

        Args:
            source_id: UUID of the first node.
            target_id: UUID of the second node.
            source_priority: If True, source is the survivor; else target.

        Returns:
            MergeResult with merge statistics.

        Raises:
            EntityNotFoundError: If either node is not found.
            ValueError: If the nodes cannot be merged (wrong types).
        """
        logger.info(
            "Merging nodes",
            extra={"source_id": str(source_id), "target_id": str(target_id)},
        )

        source = await self._node_repo.get_by_id(source_id)
        if not source:
            raise EntityNotFoundError("GraphNode", source_id)

        target = await self._node_repo.get_by_id(target_id)
        if not target:
            raise EntityNotFoundError("GraphNode", target_id)

        if source.node_type != target.node_type:
            raise ValueError(
                f"Cannot merge nodes of different types: "
                f"{source.node_type.value} vs {target.node_type.value}"
            )

        survivor: TemporalNode = source if source_priority else target
        merged: TemporalNode = target if source_priority else source

        now = datetime.now(timezone.utc)
        merged_properties: dict[str, Any] = dict(survivor.properties)
        conflict_count = 0

        for key, value in merged.properties.items():
            if key in merged_properties:
                if merged_properties[key] != value:
                    conflict_count += 1
                    if not source_priority:
                        merged_properties[key] = value
            else:
                merged_properties[key] = value

        merged_labels: list[str] = list(set(survivor.labels) | set(merged.labels))

        survivor.properties = merged_properties
        survivor.labels = merged_labels
        survivor.updated_at = now
        survivor.version = max(survivor.version, merged.version) + 1

        await self._node_repo.save(survivor)
        await self._node_repo.soft_delete(merged.id)

        merged_rel_count = await self._reparent_relationships(
            merged_id=merged.id, survivor_id=survivor.id,
        )

        result = MergeResult(
            surviving_node_id=survivor.id,
            merged_node_id=merged.id,
            merged_properties=merged_properties,
            merged_labels=merged_labels,
            conflict_count=conflict_count,
            merged_relationship_count=merged_rel_count,
        )

        logger.info(
            "Merge completed",
            extra={
                "survivor": str(result.surviving_node_id),
                "conflicts": result.conflict_count,
                "rels_reparented": result.merged_relationship_count,
            },
        )
        return result

    async def _reparent_relationships(
        self,
        merged_id: UUID,
        survivor_id: UUID,
    ) -> int:
        """Move all relationships from merged node to survivor node."""
        count = 0

        try:
            outgoing, _ = await self._rel_repo.get_by_source(
                source_id=merged_id, page=1, page_size=500,
            )
        except Exception:
            outgoing = []

        try:
            incoming, _ = await self._rel_repo.get_by_target(
                target_id=merged_id, page=1, page_size=500,
            )
        except Exception:
            incoming = []

        for rel in outgoing:
            try:
                rel.source_id = survivor_id
                await self._rel_repo.save(rel)
                count += 1
            except Exception as e:
                logger.warning("Failed to reparent outgoing rel %s: %s", rel.id, str(e))

        for rel in incoming:
            try:
                rel.target_id = survivor_id
                await self._rel_repo.save(rel)
                count += 1
            except Exception as e:
                logger.warning("Failed to reparent incoming rel %s: %s", rel.id, str(e))

        return count

    def _compute_similarity(
        self,
        a: TemporalNode,
        b: TemporalNode,
    ) -> tuple[float, list[str]]:
        """Compute similarity score between two nodes using weighted field comparison.

        Compares title, code, text (or description fallback), and name fields
        using SequenceMatcher. Returns weighted average and list of matched fields.
        """
        weights = 0.0
        weighted_sum = 0.0
        matched: list[str] = []

        for field in _WEIGHT_MAP:
            val_a = str(a.properties.get(field, "") or "")
            val_b = str(b.properties.get(field, "") or "")

            if field == "text":
                val_a = str(a.properties.get("text", a.properties.get("description", "")) or "")
                val_b = str(b.properties.get("text", b.properties.get("description", "")) or "")
                val_a = val_a[:200]
                val_b = val_b[:200]

            if not val_a or not val_b:
                continue

            sim = self._text_similarity(val_a, val_b)
            weighted_sum += sim * _WEIGHT_MAP[field]
            weights += _WEIGHT_MAP[field]
            if sim >= 0.8:
                matched.append(field)

        if weights == 0.0:
            return 0.0, []

        return weighted_sum / weights, matched

    @staticmethod
    def _blocking_key(node: TemporalNode) -> str:
        """Generate a blocking key for grouping candidate nodes.

        Uses node_type + first character of title/code to create blocks
        that are likely to contain duplicates while keeping block sizes small.
        """
        title = node.properties.get("title", "")
        code = node.properties.get("code", "")
        prefix = (title[:1] if title else code[:1] if code else "?").lower()
        return f"{node.node_type.value}|{prefix}"

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Compute similarity between two strings using SequenceMatcher."""
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
