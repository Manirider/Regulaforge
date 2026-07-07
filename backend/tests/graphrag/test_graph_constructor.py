from regulaforge.graphrag.application.graph_constructor import (
    ENTITY_PATTERNS,
    GraphConstructor,
)
from regulaforge.graphrag.domain.enums import EntityCategory


class FakeNeo4jClient:
    def __init__(self):
        self.docs = []
        self.chunks = []
        self.entities = []
        self.edges = []
        self.events = []
        self.links = []

    async def create_document_node(self, doc):
        self.docs.append(doc)

    async def create_chunk_node(self, chunk):
        self.chunks.append(chunk)

    async def create_entity_node(self, entity):
        self.entities.append(entity)

    async def create_relationship(self, edge):
        self.edges.append(edge)

    async def create_temporal_event(self, event):
        self.events.append(event)

    async def link_chunk_to_document(self, chunk_id, doc_id):
        self.links.append((chunk_id, doc_id))

    async def link_entity_to_chunk(self, entity_id, chunk_id, confidence=1.0):
        self.links.append((entity_id, chunk_id, confidence))


class TestGraphConstructor:
    async def _build_test(self, text: str, **kwargs):
        neo4j = FakeNeo4jClient()
        constructor = GraphConstructor(neo4j, chunk_size=200, chunk_overlap=20)
        params = {
            "document_id": "doc1",
            "text": text,
            "title": "Test Document",
            "source": "test_source",
            "doc_type": "regulation",
        }
        params.update(kwargs)
        result = await constructor.build_from_document(**params)
        return neo4j, result

    def test_chunking_small_text(self):
        import asyncio
        neo4j, result = asyncio.run(self._build_test("Small text."))
        assert len(neo4j.chunks) >= 1
        assert neo4j.chunks[0].document_id == "doc1"

    def test_chunking_large_text(self):
        import asyncio
        text = "Paragraph one. " * 100 + "\n\n" + "Paragraph two. " * 100
        neo4j, result = asyncio.run(self._build_test(text))
        assert len(neo4j.chunks) >= 2

    def test_entity_extraction_rbi(self):
        import asyncio
        text = "The Reserve Bank of India regulates banking. RBI sets interest rates."
        neo4j, result = asyncio.run(self._build_test(text))
        entity_names = [e.name for e in neo4j.entities]
        assert any("Reserve Bank of India" in n for n in entity_names)
        assert any("RBI" in n for n in entity_names)

    def test_entity_extraction_sebi(self):
        import asyncio
        text = "Securities and Exchange Board of India oversees market regulations."
        neo4j, result = asyncio.run(self._build_test(text))
        entity_names = [e.name for e in neo4j.entities]
        assert any("Securities and Exchange Board of India" in n for n in entity_names)

    def test_entity_extraction_amount(self):
        import asyncio
        text = "The penalty of Rs. 10,00,000 was imposed for non-compliance."
        neo4j, result = asyncio.run(self._build_test(text))
        categories = [e.category for e in neo4j.entities]
        assert EntityCategory.AMOUNT in categories

    def test_entity_extraction_date(self):
        import asyncio
        text = "The regulation was effective from 01/01/2024."
        neo4j, result = asyncio.run(self._build_test(text))
        categories = [e.category for e in neo4j.entities]
        assert EntityCategory.DATE in categories

    def test_chunk_heading_extraction(self):
        import asyncio
        text = "SECTION 1: PRELIMINARY\nThis section defines the scope."
        neo4j, result = asyncio.run(self._build_test(text))
        headings = [c.heading for c in neo4j.chunks if c.heading]
        assert any("SECTION" in h for h in headings)

    def test_temporal_event_creation(self):
        import asyncio
        text = "On 15 March 2024, the new regulation came into effect."
        neo4j, result = asyncio.run(self._build_test(text))
        assert len(neo4j.events) >= 1

    def test_entity_patterns_are_defined(self):
        assert len(ENTITY_PATTERNS) > 0
        for category, patterns in ENTITY_PATTERNS.items():
            assert isinstance(category, EntityCategory)
            assert len(patterns) > 0

    def test_chunk_overlap(self):
        import asyncio
        text = "Word " * 100
        neo4j, result = asyncio.run(self._build_test(text))
        assert result["chunks"] > 0

    def test_document_node_created(self):
        import asyncio
        neo4j, result = asyncio.run(self._build_test("Test text."))
        assert len(neo4j.docs) == 1
        assert neo4j.docs[0].title == "Test Document"

    def test_jurisdiction_and_body(self):
        import asyncio
        neo4j, result = asyncio.run(
            self._build_test(
                "Test text.",
                jurisdiction="India",
                regulatory_body="RBI",
            )
        )
        doc = neo4j.docs[0]
        assert doc.jurisdiction == "India"
        assert doc.regulatory_body == "RBI"

    def test_entity_extraction_penalty(self):
        import asyncio
        text = "The penalty of Rs. 50,00,000 was imposed by the court."
        neo4j, result = asyncio.run(self._build_test(text))
        categories = [e.category for e in neo4j.entities]
        assert EntityCategory.PENALTY in categories or EntityCategory.AMOUNT in categories

    def test_compliance_requirement_extraction(self):
        import asyncio
        text = "Every bank shall maintain a minimum capital adequacy ratio."
        neo4j, result = asyncio.run(self._build_test(text))
        categories = [e.category for e in neo4j.entities]
        assert EntityCategory.COMPLIANCE_REQUIREMENT in categories

    def test_citation_extraction(self):
        import asyncio
        text = "As per Section 45 of the Banking Regulation Act."
        neo4j, result = asyncio.run(self._build_test(text))
        categories = [e.category for e in neo4j.entities]
        assert EntityCategory.CITATION in categories

    def test_structure_result(self):
        import asyncio
        neo4j, result = asyncio.run(self._build_test("Test text."))
        assert "document_id" in result
        assert "chunks" in result
        assert "entities" in result
