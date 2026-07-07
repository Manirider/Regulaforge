# AI Features Guide

## Overview

RegulaForge leverages AI to automate and enhance regulatory compliance activities. The AI system is designed with a **provider-agnostic architecture**, supporting OpenAI, Anthropic, and Azure OpenAI as backends. All AI features include **hallucination detection**, **confidence scoring**, and **source attribution** to ensure reliability in regulated environments.

## AI Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AI ANALYSIS PIPELINE                         │
│                                                                     │
│  Document/Text Input                                                 │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────┐      ┌──────────────────┐      ┌────────────┐ │
│  │  Text Preprocessing│──▶│  Chunking &       │──▶│  Prompt     │ │
│  │  (OCR, Parsing)   │    │  Context Assembly │    │  Selection  │ │
│  └─────────────────┘      └──────────────────┘      └──────┬─────┘ │
│                                                              │      │
│         ▼                                                     ▼      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  LLM Provider (OpenAI/Anthropic)              │  │
│  │  Provider Adapter → API Call → Response Parsing              │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                             │                                       │
│                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                 Post-Processing Pipeline                      │  │
│  │                                                               │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐  │  │
│  │  │  Hallucination   │  │  Confidence      │  │  Output    │  │  │
│  │  │  Detection       │──│  Scoring         │──│  Parsing   │  │  │
│  │  │  (Multi-strategy)│  │  (Calibrated)    │  │  (JSON)    │  │  │
│  │  └──────────────────┘  └──────────────────┘  └────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                             │                                       │
│                             ▼                                       │
│                      Structured Result                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Regulation Analysis

Automatically extracts structured information from regulatory documents.

### Capabilities
- **Requirement Extraction**: Identifies and extracts individual requirements from regulation text
- **Structuring**: Organizes requirements hierarchically with parent-child relationships
- **Metadata Extraction**: Pulls jurisdiction, effective date, issuing body, category
- **Risk Assessment**: Assigns risk weights based on language and obligations
- **Cross-Reference Detection**: Identifies references to other regulations

### Example
```python
from regulaforge.ai.generation.prompt_templates import (
    PromptTemplateRegistry,
    PromptTemplateType,
)

# Get the regulation analysis template
template = PromptTemplateRegistry.get(
    PromptTemplateType.REGULATION_ANALYSIS
)

# Format the prompt
prompt = template.format_user_prompt(
    title="General Data Protection Regulation",
    code="GDPR",
    jurisdiction="EU",
    issuing_body="European Parliament",
    document_text="... full regulation text ...",
    output_format=template.get_output_format_instruction(),
)
```

## Automated Compliance Assessment

AI evaluates entities against regulatory requirements using available evidence.

### Process
1. Requirement text is loaded from the regulation
2. Entity information and context are assembled
3. Evidence documents are retrieved and summarized
4. LLM evaluates compliance based on evidence
5. Hallucination detection verifies the response
6. Confidence score is calculated
7. Result is stored as a finding or compliance determination

### Prompt Structure
```
System: You are RegulaForge AI, an expert compliance assessor...
  - Evaluate each requirement independently
  - Base assessments ONLY on provided evidence
  - Clearly distinguish compliant/partially_compliant/non_compliant
  - Assign confidence scores based on evidence quality
  - Cite specific evidence artifacts

User: Assess compliance for:
  Entity: Customer Data Platform
  Entity Type: system
  Requirement: ART-5 - Principles relating to processing
  Requirement Text: Personal data shall be processed lawfully...
  Available Evidence: [data_processing_register.pdf, consent_logs.csv]
  Previous Findings: []
```

### Output Format
```json
{
  "compliance_determination": "partially_compliant",
  "confidence_score": 0.85,
  "evidence_summary": "Consent records exist but coverage is incomplete...",
  "gaps": [
    {
      "description": "Third-party processor consent not documented",
      "severity": "high"
    }
  ],
  "risk_assessment": {
    "impact": 8.5,
    "likelihood": 7.0,
    "overall": 59.5
  },
  "remediation": "Implement centralized consent management platform",
  "source_references": ["ART-5.1(a)", "ART-7"]
}
```

## Gap Analysis

Identifies and prioritizes gaps between current practices and regulatory requirements.

### Features
- Requirement-by-requirement comparison
- Risk-based prioritization (critical → negligible)
- Root cause analysis
- Remediation effort estimation
- Trend tracking across assessments

### Risk Scoring Formula
```
Risk Score = Impact × Likelihood

Impact (0-10): Severity of non-compliance consequences
Likelihood (0-10): Probability of occurrence
Risk Level:
  - Critical:    score >= 50
  - High:        score >= 30
  - Medium:      score >= 15
  - Low:         score >= 5
  - Negligible:  score < 5
```

## Document Processing

AI-powered document processing for compliance evidence.

### Pipeline
```
Upload → Validation → Text Extraction (OCR) → Chunking
  → AI Summarization → Entity Extraction → Result Storage
```

### Supported Document Types
| Type | Examples | Processing |
|---|---|---|
| Policy Documents | Security policies, procedures | Summarization, requirement extraction |
| Compliance Reports | Audit reports, assessment outputs | Summarization, finding extraction |
| Certifications | ISO certificates, SOC reports | Validation, expiry tracking |
| Log Files | Access logs, audit trails | Pattern analysis, anomaly detection |
| Contracts | Data processing agreements | Obligation extraction |

### Processing Status
Documents go through these statuses:
- `pending` → `processing` → `completed` | `failed`

### Document Summarization
```python
from regulaforge.ai.generation.prompt_templates import (
    PromptTemplateType,
    PromptTemplateRegistry,
)

template = PromptTemplateRegistry.get(
    PromptTemplateType.DOCUMENT_SUMMARIZATION
)

prompt = template.format_user_prompt(
    title="ISO 27001 Certification",
    doc_type="certificate",
    page_count=15,
    document_text="... document text ...",
    output_format=template.get_output_format_instruction(),
)
```

## Risk Scoring

Composite risk scoring combines multiple factors:

### Factors
1. **Risk Weight** (0.0-1.0): Importance of the requirement within the regulation
2. **Impact Score** (0-10): Business impact if the requirement is not met
3. **Likelihood Score** (0-10): Probability of the risk materializing
4. **Overall Score** (0-100): Aggregate compliance score for the assessment

### Compliance Score Calculation
```
Compliance Score = 100 - (Sum of (Finding Risk × Risk Weight) / Total Risk Weight × 100)

where Finding Risk = Impact × Likelihood / 100

Example:
  3 findings with Risk Scores: 59.5 (high), 24.0 (medium), 6.0 (low)
  Risk Weights: 0.95, 0.8, 0.5
  Total risk = 59.5×0.95 + 24.0×0.8 + 6.0×0.5 = 56.5 + 19.2 + 3.0 = 78.7
  Compliance Score = 100 - 78.7 = 21.3
```

## Confidence Scores

Every AI prediction includes a calibrated confidence score.

### Scorer Components

| Component | Weight | Description |
|---|---|---|
| Evidence Quality | 35% | Quality and completeness of supporting evidence |
| Source Grounding | 30% | How well the response is grounded in source text |
| Prediction Consistency | 20% | Consistency across multiple analyses |
| Text Ambiguity | 15% | (Subtracted) Ambiguity level in regulatory text |
| Historical Accuracy | (bonus) | Historical accuracy for similar task types |

### Confidence Levels

| Score Range | Level | Meaning |
|---|---|---|
| 0.90 - 1.00 | `very_high` | Strong evidence, clear regulation text |
| 0.75 - 0.89 | `high` | Good evidence, minor uncertainties |
| 0.50 - 0.74 | `medium` | Some evidence, ambiguous regulation |
| 0.25 - 0.49 | `low` | Limited evidence, significant ambiguity |
| 0.00 - 0.24 | `very_low` | Insufficient evidence, high uncertainty |

### Using Confidence Scores
```python
from regulaforge.ai.evaluation.confidence_scorer import ConfidenceScorer

scorer = ConfidenceScorer()

result = scorer.calculate(
    evidence_quality=0.85,
    source_grounding=0.75,
    prediction_consistency=0.90,
    text_ambiguity=0.10,
    historical_accuracy=0.88,
)

print(result["level"])     # "high"
print(result["score"])     # 0.8645
```

## Hallucination Prevention

Multi-strategy system to detect and prevent AI hallucinations in compliance contexts.

### Detection Strategies

1. **Source Grounding Verification**
   - Checks that all citations in the response exist in the source text
   - Verifies article/section numbers against the regulation

2. **Numerical Consistency**
   - Validates numbers, percentages, dates against source data
   - Flags unverified numerical claims

3. **Citation Validation**
   - Ensures cited legal references (Article, Section, Regulation) are grounded
   - Prevents fabricated regulatory references

4. **Self-Consistency**
   - Detects internal contradictions within the response
   - E.g., "fully compliant" vs "non-compliant gap identified"

5. **Confidence Calibration**
   - Flags low-confidence assertions below the configurable threshold (default: 0.85)

### Hallucination Verdicts
| Risk Score | Verdict | Action |
|---|---|---|
| >= 0.8 or >= 5 issues | `critical` | Reject output, require human review |
| >= 0.5 or >= 3 issues | `high` | Flag for human review |
| >= 0.3 or >= 2 issues | `medium` | Log warning, proceed with caution |
| >= 0.1 | `low` | Minor concerns, annotate output |
| < 0.1 | `negligible` | Safe to use |

### Example Detection Result
```python
from regulaforge.ai.evaluation.hallucination_detector import (
    HallucinationDetector,
)

detector = HallucinationDetector(source_text="... regulation text ...")

result = await detector.analyze_response(
    response_text="... AI generated analysis ...",
    ai_confidence=0.72,
)

print(result["verdict"])         # "high"
print(result["risk_score"])      # 0.55
print(result["issues_found"])    # 3
print(result["requires_review"]) # True
```

### Safety Mechanisms
- **Source grounding**: Every claim must reference source text
- **Confidence threshold**: Minimum 0.85 confidence for automated decisions
- **Human-in-the-loop**: Critical findings always require human review
- **Audit trail**: All AI outputs are logged for traceability
- **Version pinning**: LLM models are pinned to specific versions for reproducibility

## Prompt Customization

Prompt templates are fully customizable through the `PromptTemplateRegistry`.

### Built-in Template Types

| Template Type | Purpose |
|---|---|
| `REGULATION_ANALYSIS` | Extract structured information from regulations |
| `COMPLIANCE_ASSESSMENT` | Evaluate entity compliance against requirements |
| `RISK_EVALUATION` | Assess risk levels for findings |
| `DOCUMENT_SUMMARIZATION` | Summarize regulatory documents |
| `ENTITY_EXTRACTION` | Extract entities from text |
| `REQUIREMENT_DECOMPOSITION` | Decompose regulations into requirements |
| `GAP_ANALYSIS` | Identify and analyze compliance gaps |
| `REPORT_GENERATION` | Generate compliance reports |
| `REMEDIATION_SUGGESTION` | Suggest remediation actions |
| `AUDIT_QUESTION_GENERATION` | Generate audit questions |

### Customizing a Template
```python
from regulaforge.ai.generation.prompt_templates import (
    PromptTemplate,
    PromptTemplateRegistry,
    PromptTemplateType,
)

custom_template = PromptTemplate(
    template_type=PromptTemplateType.REGULATION_ANALYSIS,
    system_prompt="""You are a specialized GDPR compliance analyst...""",
    user_prompt_template="""Analyze this regulation: {document_text}""",
    temperature=0.05,        # Lower temperature for more deterministic output
    max_tokens=8192,
    requires_attribution=True,
    requires_confidence=True,
)

# Register the custom template (overrides default)
PromptTemplateRegistry.register(custom_template)
```

### Configuration
```python
# settings.py
class AIConfig:
    llm_provider: str = "openai"               # openai, anthropic, azure
    llm_model: str = "gpt-4-turbo"             # Default LLM model
    llm_temperature: float = 0.1               # Response creativity (0.0-2.0)
    llm_max_tokens: int = 4096                 # Max response length
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536
    confidence_threshold: float = 0.85          # Min confidence for automation
    enable_explainability: bool = True          # Enable AI explainability
    enable_hallucination_detection: bool = True # Enable hallucination detection
    max_chunk_size: int = 4096                  # Document chunk size
```
