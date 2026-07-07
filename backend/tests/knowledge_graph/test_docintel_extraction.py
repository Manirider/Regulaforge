"""Tests for doc-intel extraction connector."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from regulaforge.knowledge_graph.application.docintel_extraction import (
    DocIntelGraphExtractor,
)
from regulaforge.knowledge_graph.domain.models import (
    GraphNodeType,
    GraphRelationshipType,
)


class TestDocIntelGraphExtractor:
    def test_extract_nodes_minimal(self) -> None:
        extractions = [
            {"entity_type": "REGULATION", "text": "GDPR Compliance Rules"},
        ]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1",
            extractions=extractions,
        )
        assert len(nodes) == 1
        node = nodes[0]
        assert node.node_type == GraphNodeType.REGULATION
        assert node.properties["source_document_id"] == "doc-1"
        assert node.properties["extracted_text"] == "GDPR Compliance Rules"
        assert node.version == 1

    def test_extract_nodes_all_types(self) -> None:
        types = ["REGULATION", "CLAUSE", "OBLIGATION", "ENTITY", "AMENDMENT",
                 "RISK_FACTOR", "CONTROL", "POLICY", "PROCEDURE", "EVIDENCE", "EVENT"]
        extractions = [{"entity_type": t, "text": f"{t} text"} for t in types]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1",
            extractions=extractions,
        )
        assert len(nodes) == len(types)

    def test_extract_nodes_with_metadata(self) -> None:
        extractions = [
            {
                "entity_type": "CLAUSE",
                "text": "Section 5: Data Protection",
                "confidence": 0.95,
                "page_number": 3,
                "metadata": {"title": "Data Protection Clause", "section": "5"},
            },
        ]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1",
            extractions=extractions,
        )
        node = nodes[0]
        assert node.properties["confidence"] == 0.95
        assert node.properties["page_number"] == 3
        assert node.properties["title"] == "Data Protection Clause"
        assert node.properties["section"] == "5"
        assert "regulation" not in node.labels
        assert "clause" in node.labels

    def test_extract_nodes_with_timestamp(self) -> None:
        ts = datetime(2025, 1, 15, tzinfo=timezone.utc)
        extractions = [{"entity_type": "REGULATION", "text": "Test"}]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1",
            extractions=extractions,
            source_timestamp=ts,
        )
        assert nodes[0].valid_from == ts

    def test_extract_relationships(self) -> None:
        extractions = [{"entity_type": "REGULATION", "text": "GDPR"}]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1", extractions=extractions,
        )
        relations = [
            {
                "source_text": "GDPR",
                "target_text": "GDPR",
                "relation_type": "REFERENCES",
                "confidence": 0.9,
            },
        ]
        rels = DocIntelGraphExtractor.extract_relationships(
            document_id="doc-1",
            extractions=relations,
            nodes=nodes,
        )
        assert len(rels) == 1
        assert rels[0].rel_type == GraphRelationshipType.REFERENCES
        assert rels[0].properties["confidence"] == 0.9

    def test_extract_relationships_no_match(self) -> None:
        nodes_list = [
            {"entity_type": "REGULATION", "text": "GDPR"},
        ]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1", extractions=nodes_list,
        )
        relations = [
            {
                "source_text": "NonExistentRegulation",
                "target_text": "AlsoNonExistent",
                "relation_type": "REFERENCES",
            },
        ]
        rels = DocIntelGraphExtractor.extract_relationships(
            document_id="doc-1",
            extractions=relations,
            nodes=nodes,
        )
        assert len(rels) == 0

    def test_extract_pipeline_result(self) -> None:
        pipeline_result = {
            "entities": [
                {"entity_type": "REGULATION", "text": "RBI Master Direction"},
                {"entity_type": "CLAUSE", "text": "Clause 4.2"},
            ],
            "relations": [
                {
                    "source_text": "RBI Master Direction",
                    "target_text": "Clause 4.2",
                    "relation_type": "DERIVES_FROM",
                },
            ],
            "metadata": {"source": "pdf_parser"},
        }
        result = DocIntelGraphExtractor.extract_pipeline_result(
            document_id="doc-1",
            pipeline_result=pipeline_result,
        )
        assert len(result["nodes"]) == 2
        assert len(result["relationships"]) >= 1
        assert result["source"] == "document_intelligence"
        assert result["document_id"] == "doc-1"

        node_types = {n.node_type for n in result["nodes"]}
        assert GraphNodeType.REGULATION in node_types
        assert GraphNodeType.CLAUSE in node_types

    def test_extract_unknown_type_defaults_to_regulation(self) -> None:
        extractions = [{"entity_type": "UNKNOWN_TYPE", "text": "Some text"}]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1", extractions=extractions,
        )
        assert nodes[0].node_type == GraphNodeType.REGULATION

    def test_extract_nodes_with_uuid_references(self) -> None:
        from uuid import uuid4
        src_id = uuid4()
        tgt_id = uuid4()
        relations = [
            {
                "source_id": str(src_id),
                "target_id": str(tgt_id),
                "relation_type": "AMENDS",
            },
        ]
        # With no matching text in nodes, relationships should still resolve
        # if UUIDs are passed directly
        nodes_list = [
            {"entity_type": "REGULATION", "text": "Source Reg"},
            {"entity_type": "REGULATION", "text": "Target Reg"},
        ]
        nodes = DocIntelGraphExtractor.extract_nodes(
            document_id="doc-1", extractions=nodes_list,
        )
        rels = DocIntelGraphExtractor.extract_relationships(
            document_id="doc-1",
            extractions=relations,
            nodes=nodes,
        )
        # UUID strings won't match text nodes, so 0 relationships expected
        assert len(rels) == 0
