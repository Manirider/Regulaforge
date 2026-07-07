"""Application layer for the XAI subsystem.

Contains explainer implementations, the main explanation orchestration
service, and natural language generation for human-readable output.
"""

from regulaforge.xai.application.counterfactual_explainer import CounterfactualExplainer
from regulaforge.xai.application.explanation_service import ExplanationService
from regulaforge.xai.application.lime_explainer import LimeExplainer
from regulaforge.xai.application.natural_language_explainer import NaturalLanguageExplainer
from regulaforge.xai.application.shap_explainer import ShapExplainer

__all__ = [
    "ShapExplainer",
    "LimeExplainer",
    "CounterfactualExplainer",
    "NaturalLanguageExplainer",
    "ExplanationService",
]
