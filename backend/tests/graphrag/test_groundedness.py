from regulaforge.graphrag.application.groundedness import GroundednessChecker
from regulaforge.graphrag.domain.enums import RetrievalStrategy
from regulaforge.graphrag.domain.models import (
    Citation,
    RankedResult,
    RetrievalResult,
    RetrievedContext,
)


def _make_context(texts: list[str]) -> RetrievedContext:
    results = []
    for i, t in enumerate(texts):
        r = RetrievalResult(
            chunk_id=f"c{i}",
            document_id=f"d{i}",
            text=t,
            score=0.9,
            strategy=RetrievalStrategy.VECTOR_ONLY,
            source="test",
        )
        results.append(RankedResult(result=r, rank=i + 1, rerank_score=0.9, original_score=0.9))
    citations = [
        Citation(document_id=f"d{i}", document_title=f"Doc {i}", source="test")
        for i in range(len(texts))
    ]
    return RetrievedContext(results=results, citations=citations)


class TestGroundednessChecker:
    def test_extract_claims(self):
        checker = GroundednessChecker()
        claims = checker._extract_claims(
            "RBI regulates banking. SEBI regulates markets. IRDAI handles insurance."
        )
        assert len(claims) == 3
        assert "RBI regulates banking" in claims[0]

    def test_extract_claims_short_sentences(self):
        checker = GroundednessChecker()
        claims = checker._extract_claims("Hi. No. RBI regulates banking.")
        # "Hi" and "No" are < 20 chars
        assert len(claims) == 1

    def test_verify_claim_grounded(self):
        checker = GroundednessChecker()
        context = _make_context([
            "The Reserve Bank of India regulates all banking operations in the country.",
        ])
        attribution = checker._verify_rule_based(
            "RBI regulates banking operations in India.",
            "\n".join(r.result.text for r in context.results),
            context.citations,
        )
        assert attribution.is_grounded is True
        assert attribution.confidence > 0.3

    def test_verify_claim_ungrounded(self):
        checker = GroundednessChecker()
        context = _make_context([
            "The weather is sunny and clear today.",
        ])
        attribution = checker._verify_rule_based(
            "RBI regulates banking operations in India.",
            "\n".join(r.result.text for r in context.results),
            context.citations,
        )
        assert attribution.is_grounded is False

    def test_find_supporting_text(self):
        checker = GroundednessChecker()
        context = "The Reserve Bank of India regulates banking.\nSEBI regulates markets."
        supporting = checker._find_supporting_text(
            "RBI regulates banking",
            context,
        )
        assert supporting is not None
        assert "Reserve Bank" in supporting

    def test_find_supporting_text_no_match(self):
        checker = GroundednessChecker()
        context = "The weather is clear."
        supporting = checker._find_supporting_text(
            "RBI regulates banking",
            context,
        )
        assert supporting is None

    def test_citation_accuracy_perfect(self):
        checker = GroundednessChecker()
        context = _make_context(["Some text"])
        accuracy = checker._check_citation_accuracy(
            "RBI regulates banking [1].",
            context,
        )
        assert accuracy == 1.0

    def test_citation_accuracy_no_refs(self):
        checker = GroundednessChecker()
        context = _make_context(["Some text"])
        accuracy = checker._check_citation_accuracy(
            "RBI regulates banking.",
            context,
        )
        assert accuracy == 0.0

    def test_check_returns_report(self):
        import asyncio

        checker = GroundednessChecker()
        context = _make_context(["RBI regulates all banking operations and compliance."])

        async def run():
            report = await checker.check(
                "RBI regulates banking operations. This ensures compliance.",
                context,
            )
            return report

        report = asyncio.run(run())
        assert report.score.overall >= 0
        assert "response" in report.__dict__
