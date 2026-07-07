"""Enterprise-grade prompt templates for regulatory AI.

All prompts are designed with:
- Clear system instructions
- Structured output formats
- Hallucination prevention mechanisms
- Source attribution requirements
- Confidence scoring
"""

from typing import Any, Optional

from regulaforge.config.constants import PromptTemplateType


class PromptTemplate:
    """Base class for all AI prompt templates.

    Each template includes system instructions, user prompt format,
    and output structure for consistent, safe AI interactions.
    """

    def __init__(
        self,
        template_type: PromptTemplateType,
        system_prompt: str,
        user_prompt_template: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        requires_attribution: bool = True,
        requires_confidence: bool = True,
    ) -> None:
        self._type = template_type
        self._system_prompt = system_prompt
        self._user_prompt_template = user_prompt_template
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._requires_attribution = requires_attribution
        self._requires_confidence = requires_confidence

    @property
    def type(self) -> PromptTemplateType:
        return self._type

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    def format_user_prompt(self, **kwargs: Any) -> str:
        """Format the user prompt with provided variables."""
        return self._user_prompt_template.format(**kwargs)

    def get_output_format_instruction(self) -> str:
        """Get instructions for structured output format."""
        instructions = []
        if self._requires_confidence:
            instructions.append(
                '- Provide a "confidence" score (0.0 to 1.0) for your response'
            )
        if self._requires_attribution:
            instructions.append(
                '- Include "source_references" citing specific sections or provisions'
            )
            instructions.append(
                '- If uncertain, state "insufficient_information" rather than guessing'
            )
        instructions.append("- Respond in valid JSON format")
        return "\n".join(instructions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self._type.value,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "requires_attribution": self._requires_attribution,
            "requires_confidence": self._requires_confidence,
            "system_prompt_preview": self._system_prompt[:200],
        }


# ---------------------------------------------------------------------------
# Template Registry
# ---------------------------------------------------------------------------

class PromptTemplateRegistry:
    """Registry of all prompt templates used in the system."""

    _templates: dict[PromptTemplateType, PromptTemplate] = {}  # noqa: RUF012

    @classmethod
    def register(cls, template: PromptTemplate) -> None:
        """Register a prompt template."""
        cls._templates[template.type] = template

    @classmethod
    def get(cls, template_type: PromptTemplateType) -> Optional[PromptTemplate]:
        """Get a template by type."""
        return cls._templates.get(template_type)

    @classmethod
    def get_all(cls) -> list[PromptTemplate]:
        """Get all registered templates."""
        return list(cls._templates.values())


# ---------------------------------------------------------------------------
# Regulation Analysis Template
# ---------------------------------------------------------------------------

REGULATION_ANALYSIS_SYSTEM = """You are RegulaForge AI, an expert regulatory compliance analyst. \
Your role is to analyze regulatory documents and extract structured information \
with high precision. You must:

1. Identify the core regulatory requirements
2. Determine applicability scope
3. Extract key dates, thresholds, and obligations
4. Identify related regulations and cross-references
5. Assess the regulatory impact level

CRITICAL RULES:
- Base all analysis ONLY on the provided text. Do not use external knowledge.
- If information is not present in the text, state "not specified" explicitly.
- Provide confidence scores for each extracted element.
- Cite specific article/section numbers from the text.
- Flag any ambiguous or unclear provisions.
- Do not interpret or extrapolate beyond the given text."""

REGULATION_ANALYSIS_USER = """Analyze the following regulatory document:

Title: {title}
Code: {code}
Jurisdiction: {jurisdiction}
Issuing Body: {issuing_body}
Document Text:
{document_text}

Provide a structured analysis including:
1. Key requirements and obligations
2. Applicable entities and scope
3. Important dates and deadlines
4. Penalties and enforcement mechanisms
5. Cross-references to other regulations
6. Critical definitions

{output_format}"""


# ---------------------------------------------------------------------------
# Compliance Assessment Template
# ---------------------------------------------------------------------------

COMPLIANCE_ASSESSMENT_SYSTEM = """You are RegulaForge AI, an expert compliance assessor. \
Your role is to evaluate an entity's compliance against specific regulatory \
requirements. You must provide evidence-based assessments.

ASSESSMENT PRINCIPLES:
1. Evaluate each requirement independently
2. Base assessments ONLY on provided evidence
3. Clearly distinguish between compliant, partially compliant, and non-compliant
4. Identify specific gaps with references to requirement text
5. Provide actionable remediation recommendations
6. Assess risk levels based on impact and likelihood

CONFIDENCE AND ATTRIBUTION:
- Assign confidence scores based on evidence quality
- Cite specific evidence artifacts
- Flag when insufficient evidence is available
- Never assume compliance without evidence"""

COMPLIANCE_ASSESSMENT_USER = """Assess compliance for the following:

Entity: {entity_name}
Entity Type: {entity_type}
Requirement: {requirement_code} - {requirement_title}
Requirement Text: {requirement_text}

Available Evidence:
{evidence}

Previous Findings: {previous_findings}

Provide:
1. Compliance determination (compliant/partially_compliant/non_compliant/insufficient_evidence)
2. Confidence score (0.0-1.0)
3. Evidence summary supporting the determination
4. Identified gaps (if any)
5. Risk assessment (impact, likelihood, overall)
6. Remediation recommendations
7. Source references

{output_format}"""


# ---------------------------------------------------------------------------
# Gap Analysis Template
# ---------------------------------------------------------------------------

GAP_ANALYSIS_SYSTEM = """You are RegulaForge AI, a compliance gap analysis specialist. \
Your role is to identify and analyze gaps between current practices and \
regulatory requirements. Be thorough, precise, and actionable.

Key principles:
- Compare each requirement against current state evidence
- Prioritize gaps by risk severity
- Identify root causes where possible
- Suggest practical remediation steps
- Estimate remediation effort and complexity"""

GAP_ANALYSIS_USER = """Perform a gap analysis for:

Regulation: {regulation_title} ({regulation_code})
Entity: {entity_name}

Requirements to assess:
{requirements}

Current State Evidence:
{current_state}

Previous Assessment Results:
{previous_assessment}

Identify and analyze each gap with:
1. Gap description and affected requirement
2. Risk severity (critical/high/medium/low)
3. Root cause analysis
4. Remediation recommendations
5. Estimated effort
6. Priority ranking

{output_format}"""


# ---------------------------------------------------------------------------
# Document Summarization Template
# ---------------------------------------------------------------------------

DOCUMENT_SUMMARIZATION_SYSTEM = """You are RegulaForge AI, a document analysis specialist. \
Extract and summarize key information from regulatory documents. \
Focus on accuracy, completeness, and actionable insights. Do not add \
information not present in the source document."""

DOCUMENT_SUMMARIZATION_USER = """Summarize the following regulatory document:

Title: {title}
Document Type: {doc_type}
Pages: {page_count}

Text:
{document_text}

Extract:
1. Executive summary (3-5 sentences)
2. Key requirements and obligations
3. Applicable entities
4. Important deadlines
5. Key definitions
6. Cross-references to other regulations
7. Regulatory impact assessment

{output_format}"""


# ---------------------------------------------------------------------------
# Register Default Templates
# ---------------------------------------------------------------------------

def register_default_templates() -> None:
    """Register all default prompt templates."""
    templates = [
        PromptTemplate(
            template_type=PromptTemplateType.REGULATION_ANALYSIS,
            system_prompt=REGULATION_ANALYSIS_SYSTEM,
            user_prompt_template=REGULATION_ANALYSIS_USER,
            temperature=0.1,
            max_tokens=4096,
        ),
        PromptTemplate(
            template_type=PromptTemplateType.COMPLIANCE_ASSESSMENT,
            system_prompt=COMPLIANCE_ASSESSMENT_SYSTEM,
            user_prompt_template=COMPLIANCE_ASSESSMENT_USER,
            temperature=0.1,
            max_tokens=4096,
        ),
        PromptTemplate(
            template_type=PromptTemplateType.GAP_ANALYSIS,
            system_prompt=GAP_ANALYSIS_SYSTEM,
            user_prompt_template=GAP_ANALYSIS_USER,
            temperature=0.2,
            max_tokens=4096,
        ),
        PromptTemplate(
            template_type=PromptTemplateType.DOCUMENT_SUMMARIZATION,
            system_prompt=DOCUMENT_SUMMARIZATION_SYSTEM,
            user_prompt_template=DOCUMENT_SUMMARIZATION_USER,
            temperature=0.1,
            max_tokens=2048,
        ),
    ]

    for template in templates:
        PromptTemplateRegistry.register(template)
