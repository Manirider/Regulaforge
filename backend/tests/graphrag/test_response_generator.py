from regulaforge.graphrag.application.response_generator import ResponseGenerator
from regulaforge.graphrag.domain.enums import RetrievalStrategy
from regulaforge.graphrag.domain.models import (
    Citation,
    RankedResult,
    RetrievalResult,
    RetrievedContext,
)


def _make_context() -> RetrievedContext:
    results = [
        RetrievalResult(
            chunk_id="c1",
            document_id="d1",
            text="The Reserve Bank of India regulates all banking operations under the Banking Regulation Act, 1949.",
            score=0.95,
            strategy=RetrievalStrategy.VECTOR_ONLY,
            source="RBI Act",
            page_number=3,
            heading="Section 1: Regulation",
        ),
        RetrievalResult(
            chunk_id="c2",
            document_id="d2",
            text="SEBI oversees securities markets and protects investor interests through various regulations.",
            score=0.85,
            strategy=RetrievalStrategy.BM25_ONLY,
            source="SEBI Act",
            page_number=5,
            heading="Chapter 1: Definitions",
        ),
    ]
    ranked = [
        RankedResult(result=r, rank=i + 1, rerank_score=0.9 - i * 0.1, original_score=r.score)
        for i, r in enumerate(results)
    ]
    citations = [
        Citation(
            document_id="d1",
            document_title="RBI Act",
            source="RBI Act",
            chunk_ids=["c1"],
            relevance_scores=[0.9],
            page_numbers=[3],
        ),
        Citation(
            document_id="d2",
            document_title="SEBI Act",
            source="SEBI Act",
            chunk_ids=["c2"],
            relevance_scores=[0.8],
            page_numbers=[5],
        ),
    ]
    return RetrievedContext(results=ranked, citations=citations, query_time_ms=42.0)


class TestResponseGenerator:
    def test_generate_rule_based(self):
        generator = ResponseGenerator()
        context = _make_context()
        response = generator._generate_rule_based(
            "Who regulates banking in India?",
            context,
        )
        assert "Query:" in response
        assert "RBI Act" in response
        assert "SEBI Act" in response

    def test_format_context(self):
        generator = ResponseGenerator()
        context = _make_context()
        formatted = generator._format_context(context)
        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "Regulation" in formatted

    def test_format_citations(self):
        generator = ResponseGenerator()
        context = _make_context()
        formatted = generator._format_citations(context.citations)
        assert "[1]" in formatted
        assert "RBI Act" in formatted
        assert "pp." in formatted

    def test_format_citations_no_pages(self):
        generator = ResponseGenerator()
        c = Citation(document_id="d1", document_title="Test Doc", source="src")
        formatted = generator._format_citations([c])
        assert "pp." not in formatted

    def test_extract_claims_with_citations(self):
        generator = ResponseGenerator()
        claims = generator.extract_claims(
            "RBI regulates banking [1]. SEBI regulates markets [2]."
        )
        assert len(claims) == 2
        assert claims[0].is_grounded is True
        assert claims[1].is_grounded is True

    def test_extract_claims_without_citations(self):
        generator = ResponseGenerator()
        claims = generator.extract_claims(
            "RBI regulates banking. SEBI regulates markets."
        )
        assert len(claims) == 0

    def test_generate_no_context(self):
        generator = ResponseGenerator()
        context = RetrievedContext(results=[], citations=[])
        response = generator._generate_rule_based("test?", context)
        assert "Query:" in response

    def test_model_name_default(self):
        generator = ResponseGenerator()
        assert generator.model_name == "gpt-4o"
