from datetime import datetime

from regulaforge.graphrag.domain.enums import (
    EntityCategory,
    GraphNodeLabel,
    GraphRelationshipType,
    RetrievalStrategy,
    TemporalRelation,
)
from regulaforge.graphrag.domain.models import (
    ChunkNode,
    Citation,
    DocumentNode,
    EntityNode,
    GraphPath,
    GraphQuery,
    GroundednessReport,
    GroundednessScore,
    RankedResult,
    RelationshipEdge,
    RetrievalResult,
    RetrievedContext,
    SourceAttribution,
    TemporalEvent,
    TemporalQuery,
    TraversalConfig,
)


class TestEnums:
    def test_graph_node_label_values(self):
        assert GraphNodeLabel.DOCUMENT.value == "Document"
        assert GraphNodeLabel.CHUNK.value == "Chunk"
        assert GraphNodeLabel.ENTITY.value == "Entity"

    def test_graph_relationship_type_values(self):
        assert GraphRelationshipType.CONTAINS.value == "CONTAINS"
        assert GraphRelationshipType.HAS_ENTITY.value == "HAS_ENTITY"
        assert GraphRelationshipType.REGULATES.value == "REGULATES"
        assert GraphRelationshipType.SUPERSEDES.value == "SUPERSEDES"

    def test_entity_category_values(self):
        assert EntityCategory.ORGANIZATION.value == "ORGANIZATION"
        assert EntityCategory.REGULATION.value == "REGULATION"
        assert EntityCategory.COMPLIANCE_REQUIREMENT.value == "COMPLIANCE_REQUIREMENT"

    def test_retrieval_strategy_values(self):
        assert RetrievalStrategy.VECTOR_ONLY.value == "vector_only"
        assert RetrievalStrategy.HYBRID_FULL.value == "hybrid_full"
        assert RetrievalStrategy.TEMPORAL.value == "temporal"

    def test_temporal_relation_values(self):
        assert TemporalRelation.AFTER.value == "AFTER"
        assert TemporalRelation.DURING.value == "DURING"
        assert TemporalRelation.EQUALS.value == "EQUALS"


class TestDomainModels:
    def test_document_node_defaults(self):
        doc = DocumentNode(
            id="doc1", title="Test", source="src", doc_type="regulation"
        )
        assert doc.id == "doc1"
        assert doc.title == "Test"
        assert doc.jurisdiction is None
        assert doc.created_at is not None

    def test_document_node_with_all_fields(self):
        dt = datetime(2024, 1, 15)
        doc = DocumentNode(
            id="doc1",
            title="RBI Circular",
            source="rbi.org",
            doc_type="circular",
            jurisdiction="India",
            regulatory_body="RBI",
            published_date=dt,
            metadata={"year": 2024},
        )
        assert doc.jurisdiction == "India"
        assert doc.regulatory_body == "RBI"
        assert doc.published_date == dt

    def test_chunk_node(self):
        chunk = ChunkNode(
            id="chunk_0001",
            document_id="doc1",
            text="Some text content",
            chunk_index=0,
            page_number=3,
            heading="Section 1",
        )
        assert chunk.document_id == "doc1"
        assert chunk.page_number == 3
        assert chunk.heading == "Section 1"

    def test_entity_node(self):
        entity = EntityNode(
            id="ent1",
            name="Reserve Bank of India",
            category=EntityCategory.ORGANIZATION,
            aliases=["RBI"],
            description="Central bank of India",
        )
        assert entity.name == "Reserve Bank of India"
        assert entity.category == EntityCategory.ORGANIZATION
        assert "RBI" in entity.aliases

    def test_relationship_edge(self):
        edge = RelationshipEdge(
            source_id="e1",
            target_id="e2",
            relationship_type=GraphRelationshipType.REGULATES,
            weight=0.9,
            confidence=0.85,
        )
        assert edge.relationship_type == GraphRelationshipType.REGULATES
        assert edge.weight == 0.9
        assert edge.confidence == 0.85

    def test_temporal_event(self):
        now = datetime.utcnow()
        event = TemporalEvent(
            id="evt1",
            name="New Regulation Effective",
            date=now,
            description="New regulation comes into effect",
            entity_ids=["e1", "e2"],
            event_type="regulation_effective",
        )
        assert event.name == "New Regulation Effective"
        assert len(event.entity_ids) == 2

    def test_graph_path(self):
        path = GraphPath(
            nodes=[{"id": "n1"}, {"id": "n2"}],
            edges=[{"source": "n1", "target": "n2"}],
            length=1,
            score=0.95,
        )
        assert path.length == 1
        assert path.score == 0.95

    def test_graph_query_defaults(self):
        q = GraphQuery()
        assert q.max_depth == 3
        assert q.limit == 20
        assert q.node_labels is None

    def test_graph_query_with_filters(self):
        q = GraphQuery(
            entity_names=["RBI", "SEBI"],
            entity_categories=[EntityCategory.ORGANIZATION],
            max_depth=4,
            min_confidence=0.5,
            limit=10,
        )
        assert "RBI" in q.entity_names
        assert len(q.entity_categories) == 1

    def test_retrieval_result(self):
        r = RetrievalResult(
            chunk_id="chunk1",
            document_id="doc1",
            text="Sample text",
            score=0.95,
            strategy=RetrievalStrategy.VECTOR_ONLY,
            source="qdrant",
        )
        assert r.chunk_id == "chunk1"
        assert r.score == 0.95
        assert r.strategy == RetrievalStrategy.VECTOR_ONLY

    def test_ranked_result(self):
        result = RetrievalResult(
            chunk_id="c1", document_id="d1", text="t",
            score=0.8, strategy=RetrievalStrategy.VECTOR_ONLY, source="s",
        )
        ranked = RankedResult(
            result=result,
            rank=1,
            rerank_score=0.95,
            original_score=0.8,
        )
        assert ranked.rank == 1
        assert ranked.rerank_score == 0.95

    def test_citation_defaults(self):
        c = Citation(
            document_id="doc1",
            document_title="Test Doc",
            source="src",
        )
        assert c.id is not None
        assert c.page_numbers == []

    def test_source_attribution(self):
        sa = SourceAttribution(
            claim="This is a claim",
            citations=[],
            confidence=0.9,
            is_grounded=True,
        )
        assert sa.claim == "This is a claim"
        assert sa.is_grounded is True

    def test_retrieved_context(self):
        ctx = RetrievedContext(
            results=[],
            citations=[],
            query_time_ms=42.5,
            strategies_used=[RetrievalStrategy.VECTOR_ONLY],
        )
        assert ctx.query_time_ms == 42.5
        assert RetrievalStrategy.VECTOR_ONLY in ctx.strategies_used

    def test_groundedness_score_defaults(self):
        gs = GroundednessScore()
        assert gs.overall == 0.0
        assert gs.faithfulness == 0.0

    def test_groundedness_report(self):
        gs = GroundednessScore(overall=0.85, faithfulness=0.9)
        report = GroundednessReport(
            response="Test response",
            claims=[],
            score=gs,
            ungrounded_claims=["bad claim"],
        )
        assert report.score.overall == 0.85
        assert "bad claim" in report.ungrounded_claims

    def test_temporal_query(self):
        tq = TemporalQuery(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            relation=TemporalRelation.DURING,
        )
        assert tq.start_date is not None

    def test_traversal_config_defaults(self):
        tc = TraversalConfig()
        assert tc.max_depth == 3
        assert tc.traversal_strategy == "bfs"

    def test_traversal_config_custom(self):
        tc = TraversalConfig(
            max_depth=5,
            min_weight=0.5,
            max_branches=20,
            traversal_strategy="dfs",
            include_metadata=False,
        )
        assert tc.max_depth == 5
        assert tc.traversal_strategy == "dfs"
