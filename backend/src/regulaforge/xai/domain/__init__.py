"""Domain models and events for the XAI subsystem.

Contains pure domain concepts — enums, dataclasses, and value objects —
free of framework dependencies and infrastructure concerns.
"""

from regulaforge.xai.domain.events import (
    CounterfactualGenerated,
    ExplanationFailed,
    ExplanationGenerated,
)
from regulaforge.xai.domain.models import (
    CounterfactualExplanation,
    Explanation,
    ExplanationRequest,
    ExplanationType,
    FeatureContribution,
    NaturalLanguageExplanation,
)

__all__ = [
    "ExplanationType",
    "Explanation",
    "FeatureContribution",
    "CounterfactualExplanation",
    "NaturalLanguageExplanation",
    "ExplanationRequest",
    "ExplanationGenerated",
    "CounterfactualGenerated",
    "ExplanationFailed",
]
