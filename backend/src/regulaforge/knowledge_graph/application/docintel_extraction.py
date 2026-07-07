"""Relationship extraction connector — converts document intelligence output to knowledge graph nodes and edges.

Transforms extracted entities and relations from the document intelligence
pipeline into TemporalNode and TemporalRelationship objects for ingestion
into the temporal knowledge graph.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.config.logging import get_logger
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
    TemporalNode,
    TemporalRelationship,
)

logger = get_logger(__name__)

_TYPE_MAP: dict[str, GraphNodeType] = {
    "REGULATION": GraphNodeType.REGULATION,
    "CLAUSE": GraphNodeType.CLAUSE,
    "OBLIGATION": GraphNodeType.OBLIGATION,
    "ENTITY": GraphNodeType.ENTITY,
    "AMENDMENT": GraphNodeType.AMENDMENT,
    "RISK_FACTOR": GraphNodeType.RISK_FACTOR,
    "CONTROL": GraphNodeType.CONTROL,
    "POLICY": GraphNodeType.POLICY,
    "PROCEDURE": GraphNodeType.PROCEDURE,
    "EVIDENCE": GraphNodeType.EVIDENCE,
    "EVENT": GraphNodeType.EVENT,
}

_RELATION_TYPE_MAP: dict[str, GraphRelationshipType] = {
    "AMENDS": GraphRelationshipType.AMENDS,
    "SUPERSEDES": GraphRelationshipType.SUPERSEDES,
    "REFERENCES": GraphRelationshipType.REFERENCES,
    "APPLIES_TO": GraphRelationshipType.APPLIES_TO,
    "CREATES_OBLIGATION": GraphRelationshipType.CREATES_OBLIGATION,
    "COMPLIES_WITH": GraphRelationshipType.COMPLIES_WITH,
    "VIOLATES": GraphRelationshipType.VIOLATES,
    "MITIGATES": GraphRelationshipType.MITIGATES,
    "DEPENDS_ON": GraphRelationshipType.DEPENDS_ON,
    "DERIVES_FROM": GraphRelationshipType.DERIVES_FROM,
    "REPLACES": GraphRelationshipType.REPLACES,
}


class DocIntelGraphExtractor:
    """Transforms document intelligence extraction results into graph entities.

    Maps extracted entities and relations from doc-intel pipelines
    to temporal graph nodes and relationships with appropriate types
    and temporal annotations.
    """

    @staticmethod
    def extract_nodes(
        document_id: str,
        extractions: list[dict[str, Any]],
        source_timestamp: Optional[datetime] = None,
    ) -> list[TemporalNode]:
        """Convert doc-intel extractions into temporal graph nodes.

        Args:
            document_id: The source document identifier.
            extractions: List of extracted entity dicts from the doc-intel pipeline.
                Each dict should have 'entity_type', 'text', and optionally
                'confidence', 'metadata', 'page_number'.
            source_timestamp: When the extraction was performed (defaults to now).

        Returns:
            List of TemporalNode objects ready for graph persistence.
        """
        now = source_timestamp or datetime.now(timezone.utc)
        nodes: list[TemporalNode] = []

        for extraction in extractions:
            entity_type_str = extraction.get("entity_type", "REGULATION").upper()
            node_type = _TYPE_MAP.get(entity_type_str, GraphNodeType.REGULATION)

            text = extraction.get("text", "")
            confidence = extraction.get("confidence", 1.0)
            metadata = extraction.get("metadata", {})
            page_number = extraction.get("page_number")

            properties: dict[str, Any] = {
                "source_document_id": document_id,
                "extracted_text": text[:5000],
                "confidence": confidence,
                "page_number": page_number,
                "extracted_at": now.isoformat(),
            }
            if isinstance(metadata, dict):
                properties.update(metadata)

            title = metadata.get("title") or text[:100]
            properties.setdefault("title", title)

            node_id = uuid4()
            node = TemporalNode(
                id=node_id,
                node_type=node_type,
                labels=[entity_type_str.lower(), "extracted"],
                properties=properties,
                valid_from=now,
                valid_to=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            nodes.append(node)

        logger.info(
            "Extracted %d graph nodes from doc-intel output",
            len(nodes),
            extra={"document_id": document_id},
        )
        return nodes

    @staticmethod
    def extract_relationships(
        document_id: str,
        extractions: list[dict[str, Any]],
        nodes: list[TemporalNode],
        source_timestamp: Optional[datetime] = None,
    ) -> list[TemporalRelationship]:
        """Convert doc-intel relations into temporal graph relationships.

        Args:
            document_id: The source document identifier.
            extractions: List of extracted relation dicts from the doc-intel pipeline.
                Each dict should have 'source_id', 'target_id', 'relation_type',
                and optionally 'confidence', 'metadata'.
            nodes: Previously extracted nodes (used for id lookup).
            source_timestamp: When the extraction was performed (defaults to now).

        Returns:
            List of TemporalRelationship objects ready for graph persistence.
        """
        now = source_timestamp or datetime.now(timezone.utc)
        node_map: dict[str, UUID] = {}
        for node in nodes:
            props = node.properties
            text = props.get("extracted_text", "")
            title = props.get("title", "")
            key = text[:100] or title[:100]
            if key:
                node_map[key] = node.id

        relationships: list[TemporalRelationship] = []

        for extraction in extractions:
            rel_type_str = extraction.get("relation_type", "REFERENCES").upper()
            rel_type = _RELATION_TYPE_MAP.get(rel_type_str, GraphRelationshipType.REFERENCES)

            source_ref = extraction.get("source_id", extraction.get("source_text", ""))
            target_ref = extraction.get("target_id", extraction.get("target_text", ""))
            confidence = extraction.get("confidence", 1.0)

            source_uuid: Optional[UUID] = None
            target_uuid: Optional[UUID] = None

            if isinstance(source_ref, str):
                for key, uid in node_map.items():
                    if source_ref[:50].lower() in key.lower():
                        source_uuid = uid
                        break
            elif isinstance(source_ref, UUID):
                source_uuid = source_ref

            if isinstance(target_ref, str):
                for key, uid in node_map.items():
                    if target_ref[:50].lower() in key.lower():
                        target_uuid = uid
                        break
            elif isinstance(target_ref, UUID):
                target_uuid = target_ref

            if source_uuid and target_uuid:
                relationship = TemporalRelationship(
                    id=uuid4(),
                    source_id=source_uuid,
                    target_id=target_uuid,
                    rel_type=rel_type,
                    properties={
                        "source_document_id": document_id,
                        "confidence": confidence,
                        "extracted_at": now.isoformat(),
                    },
                    valid_from=now,
                    valid_to=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                relationships.append(relationship)

        logger.info(
            "Extracted %d graph relationships from doc-intel output",
            len(relationships),
            extra={"document_id": document_id},
        )
        return relationships

    @staticmethod
    def extract_pipeline_result(
        document_id: str,
        pipeline_result: dict[str, Any],
        source_timestamp: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Transform a full doc-intel pipeline result into graph-ready data.

        Args:
            document_id: The source document identifier.
            pipeline_result: The full pipeline result dict from doc-intel.
                Expected keys: 'entities', 'relations', 'metadata'.
            source_timestamp: When the extraction was performed.

        Returns:
            Dictionary with 'nodes' and 'relationships' lists ready for
            the knowledge graph merge operation.
        """
        entities = pipeline_result.get("entities", [])
        relations = pipeline_result.get("relations", pipeline_result.get("relationships", []))

        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id=document_id,
            extractions=entities,
            source_timestamp=source_timestamp,
        )

        relationships = DocIntelGraphExtractor.extract_relationships(
            document_id=document_id,
            extractions=relations,
            nodes=nodes,
            source_timestamp=source_timestamp,
        )

        return {
            "nodes": nodes,
            "relationships": relationships,
            "source": "document_intelligence",
            "document_id": document_id,
        }
