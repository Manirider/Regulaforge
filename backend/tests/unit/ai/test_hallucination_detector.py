"""Unit tests for the HallucinationDetector."""

import pytest
from regulaforge.ai.evaluation.hallucination_detector import HallucinationDetector


class TestHallucinationDetection:
    """Tests for hallucination detection capabilities."""

    @pytest.fixture
    def sample_source_text(self) -> str:
        return """
        Article 5: Principles relating to processing of personal data.
        Personal data shall be processed lawfully, fairly and in a transparent manner.
        Article 17: Right to erasure (right to be forgotten).
        The data subject shall have the right to obtain erasure of personal data.
        Fines up to 20,000,000 EUR or 4% of annual turnover.
        """

    async def test_no_hallucination_with_grounded_response(self, sample_source_text):
        """Should pass a response that is well-grounded in source."""
        detector = HallucinationDetector(source_text=sample_source_text)
        response = """
        Article 5 requires lawful, fair and transparent processing of personal data.
        Article 17 provides the right to erasure.
        """
        result = await detector.analyze_response(response)
        assert result["verdict"] in ("negligible", "low")
        assert result["risk_score"] < 0.3

    async def test_detect_ungrounded_citation(self, sample_source_text):
        """Should flag a citation not in the source."""
        detector = HallucinationDetector(source_text=sample_source_text)
        response = "Article 99 requires mandatory data breach notification within 24 hours."
        result = await detector.analyze_response(response)
        assert len(result["issues"]) > 0

    async def test_detect_unverified_number(self, sample_source_text):
        """Should flag numerical claims not in source."""
        detector = HallucinationDetector(source_text=sample_source_text)
        response = "Fines up to 50000000 EUR or 10% of annual turnover."
        result = await detector.analyze_response(response)
        unverified = [i for i in result["issues"] if i["type"] == "unverified_number"]
        assert len(unverified) > 0

    async def test_detect_hallucination_indicators(self):
        """Should flag phrases that indicate potential hallucination."""
        detector = HallucinationDetector()
        response = "As we all know, this regulation requires X. Studies show that Y."
        result = await detector.analyze_response(response)
        indicators = [i for i in result["issues"] if i["type"] == "hallucination_indicator"]
        assert len(indicators) > 0

    async def test_detect_internal_contradiction(self):
        """Should detect contradictory statements."""
        detector = HallucinationDetector()
        response = "The entity is fully compliant with all requirements met. However, significant gaps were identified in data protection."
        result = await detector.analyze_response(response)
        contradictions = [i for i in result["issues"] if i["type"] == "contradiction"]
        assert len(contradictions) > 0

    async def test_low_confidence_trigger(self):
        """Should flag low confidence scores."""
        detector = HallucinationDetector()
        response = "Analysis result text here."
        result = await detector.analyze_response(response, ai_confidence=0.3)
        low_conf = [i for i in result["issues"] if i["type"] == "low_confidence"]
        assert len(low_conf) > 0

    async def test_critical_verdict_with_many_issues(self, sample_source_text):
        """Should return critical verdict with many issues."""
        detector = HallucinationDetector(source_text=sample_source_text)
        response = """
        As we all know and studies show, Article 99 requires fines of 100,000,000 EUR.
        The entity is fully compliant but has major non-compliant issues.
        Research indicates this is common knowledge in the industry.
        """
        result = await detector.analyze_response(response)
        assert result["issues_found"] >= 3

    async def test_no_source_text_available(self):
        """Should handle responses when no source text is given."""
        detector = HallucinationDetector()
        response = "Well-grounded response without source comparison."
        result = await detector.analyze_response(response)
        assert result["verdict"] in ("negligible", "low")
        assert result["risk_score"] < 0.3

    async def test_requires_review_for_high_risk(self):
        """Should flag high-risk responses for review."""
        detector = HallucinationDetector()
        response = (
            "As we all know, Article 50 requires mandatory reporting. "
            "Studies show that fines of 99,999,999 EUR apply. "
            "The entity is fully compliant with all issues present. "
            "Research indicates this requires immediate attention."
        )
        result = await detector.analyze_response(response, ai_confidence=0.2)
        assert "requires_review" in result
