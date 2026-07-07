"""Pure domain models for the Explainable AI (XAI) subsystem.

These are plain Python enums, dataclasses, and value objects — NOT
SQLAlchemy or ORM models. They represent the core domain concepts
for explaining predictions made by AI models in the compliance platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Union
from uuid import UUID, uuid4


class ExplanationType(str, Enum):
    """Supported explanation methodologies for AI model predictions."""

    SHAP = "shap"
    LIME = "lime"
    COUNTERFACTUAL = "counterfactual"
    RULE_BASED = "rule_based"
    ATTENTION = "attention"
    GRADIENT = "gradient"
    TREE_INTERPRETER = "tree_interpreter"
    ANCHOR = "anchor"


@dataclass
class FeatureContribution:
    """Value object representing a single feature's contribution to a prediction.

    Captures how each input feature influenced the model's output,
    including direction, magnitude, interactions, and human-readable context.
    """

    feature_name: str = ""
    feature_value: Union[float, str] = 0.0
    contribution: float = 0.0
    direction: str = "neutral"
    interaction_effects: list[dict[str, Any]] = field(default_factory=list)
    expected_range: Optional[tuple[float, float]] = None
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.feature_name, str) or not self.feature_name:
            raise ValueError("feature_name must be a non-empty string")
        if not isinstance(self.contribution, int | float):
            raise ValueError("contribution must be a numeric value")
        if self.direction not in ("positive", "negative", "neutral"):
            raise ValueError("direction must be one of: positive, negative, neutral")
        if not isinstance(self.interaction_effects, list):
            raise ValueError("interaction_effects must be a list")
        if self.expected_range is not None:  # noqa: SIM102
            if not isinstance(self.expected_range, list | tuple) or len(self.expected_range) != 2:
                raise ValueError("expected_range must be a tuple of (float, float) or None")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "feature_name": self.feature_name,
            "feature_value": self.feature_value,
            "contribution": self.contribution,
            "direction": self.direction,
            "interaction_effects": list(self.interaction_effects),
            "description": self.description,
        }
        if self.expected_range is not None:
            result["expected_range"] = [self.expected_range[0], self.expected_range[1]]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureContribution:
        expected_range = data.get("expected_range")
        if expected_range is not None and isinstance(expected_range, list | tuple):
            expected_range = (float(expected_range[0]), float(expected_range[1]))
        return cls(
            feature_name=data["feature_name"],
            feature_value=data.get("feature_value", 0.0),
            contribution=data.get("contribution", 0.0),
            direction=data.get("direction", "neutral"),
            interaction_effects=data.get("interaction_effects", []),
            expected_range=expected_range,
            description=data.get("description", ""),
        )


@dataclass
class CounterfactualExplanation:
    """Explanation showing minimal input changes needed for a different outcome.

    Counterfactuals answer "what would need to be different for the
    model to predict a different outcome?" — a powerful tool for
    understanding model decisions and identifying remediation paths.
    """

    id: UUID = field(default_factory=uuid4)
    original_input: dict[str, Any] = field(default_factory=dict)
    counterfactual_input: dict[str, Any] = field(default_factory=dict)
    feature_changes: list[dict[str, Any]] = field(default_factory=list)
    outcome_change: str = ""
    distance: float = 0.0
    viability: float = 1.0
    natural_language: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("id must be a UUID")
        if not isinstance(self.original_input, dict):
            raise ValueError("original_input must be a dict")
        if not isinstance(self.counterfactual_input, dict):
            raise ValueError("counterfactual_input must be a dict")
        if not isinstance(self.feature_changes, list):
            raise ValueError("feature_changes must be a list")
        if self.distance < 0:
            raise ValueError("distance must be >= 0")
        if self.viability < 0.0 or self.viability > 1.0:
            raise ValueError("viability must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "original_input": dict(self.original_input),
            "counterfactual_input": dict(self.counterfactual_input),
            "feature_changes": list(self.feature_changes),
            "outcome_change": self.outcome_change,
            "distance": self.distance,
            "viability": self.viability,
            "natural_language": self.natural_language,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CounterfactualExplanation:
        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            original_input=data.get("original_input", {}),
            counterfactual_input=data.get("counterfactual_input", {}),
            feature_changes=data.get("feature_changes", []),
            outcome_change=data.get("outcome_change", ""),
            distance=data.get("distance", 0.0),
            viability=data.get("viability", 1.0),
            natural_language=data.get("natural_language", ""),
        )


@dataclass
class NaturalLanguageExplanation:
    """Human-readable explanation of an AI model's prediction.

    Adapts content based on audience (technical, compliance officer,
    executive, regulator) and detail level, including key factors,
    risk assessment, recommended actions, and regulatory citations.
    """

    explanation_text: str = ""
    key_factors: list[str] = field(default_factory=list)
    risk_level_statement: str = ""
    recommended_actions: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    uncertainty_statement: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.explanation_text, str):
            raise ValueError("explanation_text must be a string")
        if not isinstance(self.key_factors, list):
            raise ValueError("key_factors must be a list")
        if not isinstance(self.recommended_actions, list):
            raise ValueError("recommended_actions must be a list")
        if not isinstance(self.citations, list):
            raise ValueError("citations must be a list")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "explanation_text": self.explanation_text,
            "key_factors": list(self.key_factors),
            "risk_level_statement": self.risk_level_statement,
            "recommended_actions": list(self.recommended_actions),
            "citations": list(self.citations),
        }
        if self.uncertainty_statement is not None:
            result["uncertainty_statement"] = self.uncertainty_statement
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NaturalLanguageExplanation:
        return cls(
            explanation_text=data.get("explanation_text", ""),
            key_factors=data.get("key_factors", []),
            risk_level_statement=data.get("risk_level_statement", ""),
            recommended_actions=data.get("recommended_actions", []),
            citations=data.get("citations", []),
            uncertainty_statement=data.get("uncertainty_statement"),
        )


@dataclass
class Explanation:
    """Core domain entity representing an explanation of an AI prediction.

    Aggregates feature-level contributions, a human-readable summary,
    confidence metrics, and visualization data for rendering
    interactive explanations in the user interface.
    """

    id: UUID = field(default_factory=uuid4)
    prediction_id: UUID = field(default_factory=uuid4)
    model_name: str = ""
    explanation_type: ExplanationType = ExplanationType.SHAP
    features: list[FeatureContribution] = field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    visualization_data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("id must be a UUID")
        if not isinstance(self.prediction_id, UUID):
            raise ValueError("prediction_id must be a UUID")
        if not isinstance(self.model_name, str) or not self.model_name:
            raise ValueError("model_name must be a non-empty string")
        if not isinstance(self.explanation_type, ExplanationType):
            raise ValueError("explanation_type must be an ExplanationType enum")
        if not isinstance(self.features, list):
            raise ValueError("features must be a list")
        if not all(isinstance(f, FeatureContribution) for f in self.features):
            raise ValueError("all features must be FeatureContribution instances")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(self.visualization_data, dict):
            raise ValueError("visualization_data must be a dict")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "prediction_id": str(self.prediction_id),
            "model_name": self.model_name,
            "explanation_type": self.explanation_type.value,
            "features": [f.to_dict() for f in self.features],
            "summary": self.summary,
            "confidence": self.confidence,
            "visualization_data": dict(self.visualization_data),
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Explanation:
        features_data = data.get("features", [])
        features = [
            FeatureContribution.from_dict(fd) if isinstance(fd, dict) else fd
            for fd in features_data
        ]
        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            prediction_id=UUID(data["prediction_id"]) if isinstance(data["prediction_id"], str) else data["prediction_id"],  # noqa: E501
            model_name=data.get("model_name", ""),
            explanation_type=ExplanationType(data.get("explanation_type", "shap")),
            features=features,
            summary=data.get("summary", ""),
            confidence=data.get("confidence", 1.0),
            visualization_data=data.get("visualization_data", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else data.get("timestamp", datetime.now(timezone.utc)),  # noqa: E501
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExplanationRequest:
    """Request value object for generating explanations.

    Specifies what kind of explanation to generate, for which audience,
    at what level of detail, and with what constraints.
    """

    prediction_id: UUID = field(default_factory=uuid4)
    explanation_types: list[ExplanationType] = field(default_factory=lambda: [ExplanationType.SHAP])
    audience: str = "technical"
    detail_level: str = "detailed"
    include_visualizations: bool = True
    max_features: int = 20
    language: str = "en"

    def __post_init__(self) -> None:
        if not isinstance(self.prediction_id, UUID):
            raise ValueError("prediction_id must be a UUID")
        if not isinstance(self.explanation_types, list) or not self.explanation_types:
            raise ValueError("explanation_types must be a non-empty list of ExplanationType")
        if not all(isinstance(et, ExplanationType) for et in self.explanation_types):
            raise ValueError("all explanation_types must be ExplanationType enum values")
        valid_audiences = ("technical", "compliance_officer", "executive", "regulator")
        if self.audience not in valid_audiences:
            raise ValueError(f"audience must be one of: {valid_audiences}")
        valid_detail = ("basic", "detailed", "comprehensive")
        if self.detail_level not in valid_detail:
            raise ValueError(f"detail_level must be one of: {valid_detail}")
        if self.max_features < 1:
            raise ValueError("max_features must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": str(self.prediction_id),
            "explanation_types": [et.value for et in self.explanation_types],
            "audience": self.audience,
            "detail_level": self.detail_level,
            "include_visualizations": self.include_visualizations,
            "max_features": self.max_features,
            "language": self.language,
        }
