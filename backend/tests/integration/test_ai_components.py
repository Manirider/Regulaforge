"""Integration tests for AI components.

Tests the real TextProcessor, HallucinationDetector, ConfidenceScorer,
and PromptTemplateRegistry components working together with realistic inputs.
"""

import pytest
from regulaforge.ai.evaluation.confidence_scorer import ConfidenceScorer
from regulaforge.ai.evaluation.hallucination_detector import HallucinationDetector
from regulaforge.ai.generation.prompt_templates import (
    PromptTemplate,
    PromptTemplateRegistry,
    register_default_templates,
)
from regulaforge.ai.nlp.text_processor import TextProcessor
from regulaforge.config.constants import PromptTemplateType

pytestmark = pytest.mark.integration


class TestTextProcessorChunking:
    """TextProcessor.chunk_text with sample regulatory text."""

    @pytest.fixture
    def processor(self) -> TextProcessor:
        return TextProcessor()

    @pytest.fixture
    def sample_regulatory_text(self) -> str:
        return """Article 5: Principles relating to processing of personal data.

Personal data shall be processed lawfully, fairly and in a transparent manner.
Processing shall be adequate, relevant and limited to what is necessary.

Article 6: Lawfulness of processing.

Processing shall be lawful only if at least one of the following applies:
(a) the data subject has given consent;
(b) processing is necessary for the performance of a contract.

Article 17: Right to erasure (right to be forgotten).

The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay.

Fines up to 20,000,000 EUR or 4% of annual turnover, whichever is higher.
"""

    def test_text_processor_chunking(self, processor, sample_regulatory_text):
        chunks = processor.chunk_text(sample_regulatory_text)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert "text" in chunk
            assert "index" in chunk
            assert "metadata" in chunk
            assert chunk["index"] >= 0
            assert len(chunk["text"]) > 0

    def test_text_processor_empty_text(self, processor):
        chunks = processor.chunk_text("")
        assert chunks == []

    def test_text_processor_clean_text(self, processor):
        processor._chunk_size = 10000
        cleaned = processor.clean_text("  Hello   World  \n\n  Test  ")
        assert cleaned == "Hello World Test"


class TestTextProcessorSections:
    """TextProcessor.extract_sections with regulation-like text."""

    @pytest.fixture
    def processor(self) -> TextProcessor:
        return TextProcessor()

    @pytest.fixture
    def hierarchical_text(self) -> str:
        return """Article 1: Subject matter

This Regulation lays down rules concerning the protection of natural persons.

Article 2: Material scope

This Regulation applies to the processing of personal data wholly or partly by automated means.

Section 1: General provisions

The controller shall be responsible for compliance.

Chapter II: Principles

Any processing must comply with the principles relating to processing of personal data.
"""

    def test_text_processor_sections(self, processor, hierarchical_text):
        sections = processor.extract_sections(hierarchical_text)

        assert len(sections) >= 3
        titles = [s["title"] for s in sections]
        assert any("Article 1" in t for t in titles)
        assert any("Article 2" in t for t in titles)
        for section in sections:
            assert "title" in section
            assert "level" in section
            assert "content" in section

    def test_extract_sections_empty(self, processor):
        sections = processor.extract_sections("")
        assert len(sections) == 0

    def test_extract_sections_no_headers(self, processor):
        text = "Just a paragraph of plain text without any article or section headers."
        sections = processor.extract_sections(text)
        assert len(sections) >= 1
        assert sections[0]["title"] == "Preamble"


class TestTextProcessorCitations:
    """TextProcessor.extract_citations."""

    @pytest.fixture
    def processor(self) -> TextProcessor:
        return TextProcessor()

    def test_extract_article_citations(self, processor):
        text = "As per Art. 5(1) and Article 17, the controller must comply."
        citations = processor.extract_citations(text)

        assert len(citations) >= 2
        assert any("5" in c for c in citations)
        assert any("17" in c for c in citations)

    def test_extract_section_citations(self, processor):
        text = "See Section 404 of the regulation and Sec. 302."
        citations = processor.extract_citations(text)

        assert len(citations) >= 2

    def test_extract_no_citations(self, processor):
        text = "This text contains no regulatory citations whatsoever."
        citations = processor.extract_citations(text)

        assert citations == []

    def test_extract_regulation_citations(self, processor):
        text = "Reg. 2016/679 and Regulation 2023/2854 apply."
        citations = processor.extract_citations(text)

        assert len(citations) >= 2


class TestHallucinationDetectorFull:
    """Full flow HallucinationDetector with source text and response."""

    @pytest.fixture
    def sample_source_text(self) -> str:
        return """
        Article 5: Principles relating to processing of personal data.
        Personal data shall be processed lawfully, fairly and in a transparent manner.
        Article 17: Right to erasure (right to be forgotten).
        The data subject shall have the right to obtain erasure of personal data.
        Fines up to 20,000,000 EUR or 4% of annual turnover.
        """

    async def test_hallucination_detector_clean_response(self, sample_source_text):
        detector = HallucinationDetector(source_text=sample_source_text)
        response = """
        Article 5 requires lawful, fair and transparent processing.
        Article 17 provides the right to erasure.
        """
        result = await detector.analyze_response(response)

        assert "verdict" in result
        assert "risk_score" in result
        assert "issues" in result
        assert "issues_found" in result
        assert result["risk_score"] < 0.3

    async def test_hallucination_detector_flagged_response(self, sample_source_text):
        detector = HallucinationDetector(source_text=sample_source_text)
        response = """
        As we all know, Article 99 requires mandatory reporting within 24 hours.
        Studies show fines of 100,000,000 EUR apply.
        """
        result = await detector.analyze_response(response)

        assert result["issues_found"] > 0
        assert result["risk_score"] > 0.3

    async def test_hallucination_detector_no_source(self):
        detector = HallucinationDetector()
        response = "General response without source comparison."
        result = await detector.analyze_response(response)

        assert result["verdict"] in ("negligible", "low")

    async def test_hallucination_detector_low_confidence(self, sample_source_text):
        detector = HallucinationDetector(source_text=sample_source_text)
        response = "Analysis result."
        result = await detector.analyze_response(response, ai_confidence=0.2)

        low_conf = [i for i in result["issues"] if i["type"] == "low_confidence"]
        assert len(low_conf) > 0


class TestConfidenceScorer:
    """ConfidenceScorer.calculate with various inputs."""

    @pytest.fixture
    def scorer(self) -> ConfidenceScorer:
        return ConfidenceScorer()

    def test_confidence_scorer_high_quality(self, scorer):
        result = scorer.calculate(
            evidence_quality=0.95,
            source_grounding=0.90,
            prediction_consistency=0.95,
            text_ambiguity=0.05,
        )

        assert result["score"] >= 0.7
        assert result["level"] in ("very_high", "high", "medium")
        assert "components" in result
        assert "weights" in result

    def test_confidence_scorer_low_quality(self, scorer):
        result = scorer.calculate(
            evidence_quality=0.2,
            source_grounding=0.1,
            prediction_consistency=0.3,
            text_ambiguity=0.8,
        )

        assert result["score"] < 0.5

    def test_confidence_scorer_with_historical(self, scorer):
        result = scorer.calculate(
            evidence_quality=0.8,
            source_grounding=0.7,
            prediction_consistency=0.8,
            text_ambiguity=0.2,
            historical_accuracy=0.95,
        )

        assert 0.0 <= result["score"] <= 1.0

    def test_confidence_scorer_boundary_values(self, scorer):
        result = scorer.calculate(
            evidence_quality=1.0,
            source_grounding=1.0,
            prediction_consistency=1.0,
            text_ambiguity=0.0,
        )

        assert result["score"] == 0.85
        assert result["level"] == "high"

    def test_confidence_scorer_invalid_values(self, scorer):
        with pytest.raises(ValueError):
            scorer.calculate(evidence_quality=1.5, source_grounding=0.5, prediction_consistency=0.5, text_ambiguity=0.0)

    def test_assess_evidence_quality(self, scorer):
        evidence = [
            {"is_verified": True, "type": "certificate", "source": "external_auditor", "date": "2024-01-01"},
            {"is_verified": False, "type": "report", "source": "internal"},
        ]
        score = scorer.assess_evidence_quality(evidence)
        assert 0.0 <= score <= 1.0

    def test_assess_evidence_quality_empty(self, scorer):
        score = scorer.assess_evidence_quality([])
        assert score == 0.0

    def test_assess_source_grounding(self, scorer):
        source_cites = ["5", "17", "32"]
        response_cites = ["5", "17", "99"]
        score = scorer.assess_source_grounding(source_cites, response_cites)
        assert 0.0 <= score <= 1.0

    def test_assess_source_grounding_no_response_cites(self, scorer):
        score = scorer.assess_source_grounding(["5", "17"], [])
        assert score == 0.5

    def test_update_historical_accuracy(self, scorer):
        scorer.update_historical_accuracy("regulation_analysis", True)
        acc = scorer.get_historical_accuracy("regulation_analysis")
        assert acc is not None
        assert acc >= 0.5


class TestPromptTemplates:
    """PromptTemplateRegistry and formatting."""

    def test_register_and_get_template(self):
        registry = PromptTemplateRegistry()
        template = PromptTemplate(
            template_type=PromptTemplateType.REGULATION_ANALYSIS,
            system_prompt="You are a compliance analyst.",
            user_prompt_template="Analyze: {title} - {code}",
        )
        registry.register(template)

        retrieved = registry.get(PromptTemplateType.REGULATION_ANALYSIS)
        assert retrieved is not None
        assert retrieved.type == PromptTemplateType.REGULATION_ANALYSIS

    def test_get_nonexistent_template(self):
        registry = PromptTemplateRegistry()
        result = registry.get(PromptTemplateType.GAP_ANALYSIS)
        assert result is None

    def test_get_all_templates(self):
        registry = PromptTemplateRegistry()
        t1 = PromptTemplate(
            template_type=PromptTemplateType.REGULATION_ANALYSIS,
            system_prompt="Analyze",
            user_prompt_template="{text}",
        )
        t2 = PromptTemplate(
            template_type=PromptTemplateType.COMPLIANCE_ASSESSMENT,
            system_prompt="Assess",
            user_prompt_template="{text}",
        )
        registry.register(t1)
        registry.register(t2)

        all_t = registry.get_all()
        assert len(all_t) == 2

    def test_format_user_prompt(self):
        template = PromptTemplate(
            template_type=PromptTemplateType.REGULATION_ANALYSIS,
            system_prompt="Analyze",
            user_prompt_template="Title: {title}, Code: {code}",
        )
        result = template.format_user_prompt(title="GDPR", code="GDPR-001")
        assert result == "Title: GDPR, Code: GDPR-001"

    def test_output_format_instruction_confidence_and_attribution(self):
        template = PromptTemplate(
            template_type=PromptTemplateType.REGULATION_ANALYSIS,
            system_prompt="Analyze",
            user_prompt_template="{text}",
            requires_confidence=True,
            requires_attribution=True,
        )
        instruction = template.get_output_format_instruction()
        assert "confidence" in instruction
        assert "source_references" in instruction
        assert "JSON" in instruction

    def test_output_format_instruction_basic(self):
        template = PromptTemplate(
            template_type=PromptTemplateType.REGULATION_ANALYSIS,
            system_prompt="Analyze",
            user_prompt_template="{text}",
            requires_confidence=False,
            requires_attribution=False,
        )
        instruction = template.get_output_format_instruction()
        assert instruction == "- Respond in valid JSON format"

    def test_to_dict(self):
        template = PromptTemplate(
            template_type=PromptTemplateType.REGULATION_ANALYSIS,
            system_prompt="You are an expert.",
            user_prompt_template="Analyze: {text}",
        )
        data = template.to_dict()
        assert data["type"] == PromptTemplateType.REGULATION_ANALYSIS.value
        assert data["temperature"] == 0.1
        assert "system_prompt_preview" in data

    def test_properties(self):
        template = PromptTemplate(
            template_type=PromptTemplateType.GAP_ANALYSIS,
            system_prompt="System",
            user_prompt_template="{text}",
            temperature=0.5,
            max_tokens=2048,
        )
        assert template.temperature == 0.5
        assert template.max_tokens == 2048
        assert template.type == PromptTemplateType.GAP_ANALYSIS

    def test_default_templates_registration(self):
        register_default_templates()

        assert PromptTemplateRegistry.get(PromptTemplateType.REGULATION_ANALYSIS) is not None
        assert PromptTemplateRegistry.get(PromptTemplateType.COMPLIANCE_ASSESSMENT) is not None
        assert PromptTemplateRegistry.get(PromptTemplateType.GAP_ANALYSIS) is not None
        assert PromptTemplateRegistry.get(PromptTemplateType.DOCUMENT_SUMMARIZATION) is not None
