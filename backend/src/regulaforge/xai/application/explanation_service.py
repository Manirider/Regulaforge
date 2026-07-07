"""Main orchestration service for the XAI subsystem.

Provides a unified facade for generating, caching, comparing, and
retrieving explanations across all explanation methodologies.
Coordinates explainers, natural language generation, and event publishing.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.application.ports.event_publisher import (
    EventPublisher,
    EventPublishError,
)
from regulaforge.application.ports.llm_provider import LLMProvider
from regulaforge.config.logging import get_logger
from regulaforge.xai.application.counterfactual_explainer import (
    CounterfactualExplainer,
)
from regulaforge.xai.application.lime_explainer import LimeExplainer
from regulaforge.xai.application.natural_language_explainer import (
    NaturalLanguageExplainer,
)
from regulaforge.xai.application.shap_explainer import ShapExplainer
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
)

logger = get_logger(__name__)


class ModelRegistry(ABC):
    """Port interface for loading ML models by identifier."""

    @abstractmethod
    async def load_model(self, model_id: str) -> Any:
        """Load an ML model by its registry identifier."""
        ...


class ExplanationService:
    """Main facade for the XAI subsystem.

    Coordinates all explainers, manages caching, publishes events,
    and provides a single entry point for all explanation-related
    operations in the compliance platform.
    """

    def __init__(
        self,
        shap_explainer: Optional[ShapExplainer] = None,
        lime_explainer: Optional[LimeExplainer] = None,
        counterfactual_explainer: Optional[CounterfactualExplainer] = None,
        nl_explainer: Optional[NaturalLanguageExplainer] = None,
        event_publisher: Optional[EventPublisher] = None,
        llm_provider: Optional[LLMProvider] = None,
        model_registry: Optional[ModelRegistry] = None,
        cache_size: int = 500,
    ) -> None:
        self._shap = shap_explainer or ShapExplainer()
        self._lime = lime_explainer or LimeExplainer()
        self._cf = counterfactual_explainer or CounterfactualExplainer()
        self._nl = nl_explainer or NaturalLanguageExplainer(llm_provider=llm_provider)
        self._event_publisher = event_publisher
        self._model_registry = model_registry
        self._cache: dict[str, Explanation] = {}
        self._cache_size = cache_size
        self._explanations: dict[UUID, Explanation] = {}
        self._counterfactuals: dict[UUID, CounterfactualExplanation] = {}

        logger.info(
            "ExplanationService initialized: cache_size=%d, event_publisher=%s",
            cache_size, event_publisher is not None,
        )

    async def _load_model(self, model_id: str) -> Any:
        """Load a model from the registry by its identifier.

        Args:
            model_id: The model's registry identifier.

        Returns:
            The loaded ML model.

        Raises:
            ValueError: If no model registry is configured or model not found.
        """
        if self._model_registry is None:
            raise ValueError(
                "No model registry configured. Cannot load model. "
                "Set model_registry in ExplanationService constructor."
            )
        model = await self._model_registry.load_model(model_id)
        if model is None:
            raise ValueError(f"Model '{model_id}' not found in registry.")
        return model

    async def explain_prediction(
        self,
        model_id: str,
        features: dict[str, float],
        feature_names: Optional[list[str]] = None,
        request: Optional[ExplanationRequest] = None,
    ) -> dict[str, Any]:
        """Generate explanations for a prediction using the full pipeline.

        Args:
            model_id: Model identifier for lookup in the model registry.
            features: Feature name to value mapping.
            feature_names: Names of features in order.
            request: Configuration for the explanation generation.

        Returns:
            Dict containing explanations, natural language summary,
            counterfactuals (if requested), and visualization data.
        """
        if request is None:
            request = ExplanationRequest(
                prediction_id=uuid4(),
                explanation_types=[ExplanationType.SHAP, ExplanationType.LIME],
                audience="technical",
                detail_level="detailed",
                include_visualizations=True,
                max_features=20,
            )

        model = await self._load_model(model_id)
        x = list(features.values())
        if feature_names is None:
            feature_names = list(features.keys())

        cache_key = self._build_cache_key(model, x, request)
        cached = self._check_cache(cache_key)
        if cached is not None:
            logger.debug("Returning cached explanation for key=%s", cache_key[:16])
            return cached

        result: dict[str, Any] = {
            "prediction_id": str(request.prediction_id),
            "explanations": [],
            "natural_language": None,
            "counterfactual": None,
            "visualizations": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        for exp_type in request.explanation_types:
            try:
                explanation = await self._generate_explanation(
                    model, x, feature_names, exp_type, request
                )

                if request.include_visualizations and explanation.visualization_data:
                    result["visualizations"][exp_type.value] = explanation.visualization_data

                result["explanations"].append(explanation.to_dict())

                if self._event_publisher is not None:
                    try:
                        await self._event_publisher.publish(
                            ExplanationGenerated(
                                explanation_id=explanation.id,
                                prediction_id=request.prediction_id,
                                model_name=explanation.model_name,
                                explanation_type=exp_type.value,
                                confidence=explanation.confidence,
                            )
                        )
                    except EventPublishError as epe:
                        logger.warning("Failed to publish event: %s", epe)

            except Exception as exc:
                logger.error(
                    "Failed to generate %s explanation: %s",
                    exp_type.value, exc, exc_info=True,
                )
                if self._event_publisher is not None:
                    with contextlib.suppress(EventPublishError):
                        await self._event_publisher.publish(
                            ExplanationFailed(
                                prediction_id=request.prediction_id,
                                explanation_type=exp_type.value,
                                error_message=str(exc),
                            )
                        )

        if result["explanations"]:
            best_exp_data = result["explanations"][0]
            best_exp = Explanation.from_dict(best_exp_data)
            try:
                nl = await self._nl.generate_explanation(
                    best_exp,
                    audience=request.audience,
                    detail_level=request.detail_level,
                )
                result["natural_language"] = nl.to_dict()
            except Exception as exc:
                logger.error("Failed to generate NL explanation: %s", exc)

        self._set_cache(cache_key, result)
        return result

    async def get_explanation(
        self,
        explanation_id: UUID,
    ) -> Optional[Explanation]:
        """Retrieve a previously generated explanation by ID.

        Args:
            explanation_id: UUID of the explanation.

        Returns:
            Explanation if found, None otherwise.
        """
        return self._explanations.get(explanation_id)

    async def compare_explanations(
        self,
        prediction_ids: list[UUID],
        model_id: str,
    ) -> dict[str, Any]:
        """Compare explanations across multiple predictions.

        Args:
            prediction_ids: List of prediction UUIDs to compare.
            model_id: Model identifier from the model registry.

        Returns:
            Dict with comparison data including feature agreement, conflict,
            and aggregate importance.
        """
        _ = model_id  # Reserved for future cross-model comparison
        comparisons: list[dict[str, Any]] = []
        all_features: dict[str, list[float]] = {}

        for _i, pid in enumerate(prediction_ids):
            explanation = self._explanations.get(pid)
            if explanation is None:
                comparisons.append({
                    "prediction_id": str(pid),
                    "status": "not_found",
                })
                continue

            exp_dict = explanation.to_dict()
            comparisons.append(exp_dict)

            for feature in explanation.features:
                if feature.feature_name not in all_features:
                    all_features[feature.feature_name] = []
                all_features[feature.feature_name].append(feature.contribution)

        feature_summary: dict[str, Any] = {}
        for fname, contributions in all_features.items():
            if contributions:
                feature_summary[fname] = {
                    "mean": float(np_mean(contributions)),
                    "std": float(np_std(contributions)),
                    "min": float(min(contributions)),
                    "max": float(max(contributions)),
                    "positive_count": sum(1 for c in contributions if c > 0),
                    "negative_count": sum(1 for c in contributions if c < 0),
                }

        return {
            "comparisons": comparisons,
            "count": len(comparisons),
            "feature_summary": feature_summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_feature_importance_overall(
        self,
        model_name: str,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """Get overall feature importance aggregated across explanations.

        Args:
            model_name: Name of the model to aggregate importance for.
            top_n: Number of top features to return.

        Returns:
            List of feature importance dicts sorted by absolute contribution.
        """
        feature_agg: dict[str, list[float]] = {}

        for exp in self._explanations.values():
            if exp.model_name == model_name:
                for feature in exp.features:
                    if feature.feature_name not in feature_agg:
                        feature_agg[feature.feature_name] = []
                    feature_agg[feature.feature_name].append(feature.contribution)

        result: list[dict[str, Any]] = []
        for fname, contributions in feature_agg.items():
            mean_contrib = float(np_mean(contributions))
            result.append({
                "feature_name": fname,
                "importance": mean_contrib,
                "abs_importance": abs(mean_contrib),
                "direction": "positive" if mean_contrib > 0 else "negative" if mean_contrib < 0 else "neutral",
                "sample_count": len(contributions),
            })

        result.sort(key=lambda x: x["abs_importance"], reverse=True)
        return result[:top_n]

    async def generate_counterfactual(
        self,
        model_id: str,
        x_sample: dict[str, float],
        desired_outcome: float,
        feature_ranges: Optional[dict[str, tuple[float, float]]] = None,
    ) -> dict[str, Any]:
        """Generate a counterfactual explanation.

        Args:
            model_id: Model identifier from the model registry.
            x_sample: Original sample as feature dict.
            desired_outcome: Desired target outcome.
            feature_ranges: Optional bounds for feature values.

        Returns:
            Counterfactual explanation as dict.
        """
        model = await self._load_model(model_id)
        cf = self._cf.generate_counterfactual(
            model, x_sample, desired_outcome, feature_ranges
        )
        self._counterfactuals[cf.id] = cf

        if self._event_publisher is not None:
            try:
                await self._event_publisher.publish(
                    CounterfactualGenerated(
                        counterfactual_id=cf.id,
                        prediction_id=UUID(int=0),
                        outcome_change=cf.outcome_change,
                        distance=cf.distance,
                        viability=cf.viability,
                    )
                )
            except EventPublishError as epe:
                logger.warning("Failed to publish counterfactual event: %s", epe)

        return cf.to_dict()

    async def what_if(
        self,
        x_sample: Any,
        feature_changes: dict[str, float],
    ) -> dict[str, Any]:
        """Perform what-if analysis by modifying specified features.

        Args:
            x_sample: Original sample.
            feature_changes: Dict of feature names/indices to new values.

        Returns:
            What-if analysis result.
        """
        return self._cf.generate_what_if(x_sample, feature_changes)

    async def _generate_explanation(
        self,
        model: Any,
        x: Any,
        feature_names: Optional[list[str]],
        exp_type: ExplanationType,
        request: ExplanationRequest,
    ) -> Explanation:
        """Route to the appropriate explainer based on explanation type."""
        if exp_type == ExplanationType.SHAP:
            explanation = self._shap.explain_prediction(model, x, feature_names)
        elif exp_type == ExplanationType.TREE_INTERPRETER:
            explanation = self._shap.explain_tree_model(model, x, feature_names)
        elif exp_type == ExplanationType.LIME:
            explanation = self._lime.explain_prediction(
                model, x, feature_names, request.max_features
            )
        elif exp_type == ExplanationType.COUNTERFACTUAL:
            raise NotImplementedError(
                "Counterfactual as primary explanation type not supported. "
                "Use generate_counterfactual() instead."
            )
        elif exp_type in (
            ExplanationType.RULE_BASED,
            ExplanationType.ATTENTION,
            ExplanationType.GRADIENT,
            ExplanationType.ANCHOR,
        ):
            explanation = self._fallback_explanation(
                model, x, feature_names, exp_type
            )
        else:
            raise ValueError(f"Unsupported explanation type: {exp_type}")

        explanation.prediction_id = request.prediction_id
        self._explanations[explanation.id] = explanation
        return explanation

    def _fallback_explanation(
        self,
        model: Any,
        x: Any,
        feature_names: Optional[list[str]],
        exp_type: ExplanationType,
    ) -> Explanation:
        """Generate a fallback explanation for unsupported types."""
        import numpy as np

        x_arr = np.array(x, dtype=float)
        if x_arr.ndim == 1:
            x_arr = x_arr.reshape(1, -1)

        n = x_arr.shape[1]
        feature_names or [f"feature_{i}" for i in range(n)]

        return Explanation(
            prediction_id=uuid4(),
            model_name=getattr(model, "__class__", type(model)).__name__ if model else "unknown",
            explanation_type=exp_type,
            features=[],
            summary=f"{exp_type.value} explanation type is not yet fully implemented. "
                    f"Using fallback with no feature contributions.",
            confidence=0.3,
            metadata={
                "method": "fallback",
                "requested_type": exp_type.value,
            },
        )

    def _build_cache_key(
        self,
        model: Any,
        x: Any,
        request: ExplanationRequest,
    ) -> str:
        """Build a deterministic cache key from the request."""
        import numpy as np

        x_hash = hashlib.md5(
            np.array(x, dtype=float).tobytes()
        ).hexdigest()
        model_name = getattr(model, "__class__", type(model)).__name__ if model else "none"
        req_hash = hashlib.md5(
            json.dumps(request.to_dict(), sort_keys=True).encode()
        ).hexdigest()
        return f"{model_name}:{x_hash}:{req_hash}"

    def _check_cache(self, key: str) -> Optional[dict[str, Any]]:
        """Check if a cached result exists for the given key."""
        return self._cache.get(key)

    def _set_cache(self, key: str, value: dict[str, Any]) -> None:
        """Cache a result, evicting oldest if at capacity."""
        if len(self._cache) >= self._cache_size:
            evict_key = next(iter(self._cache))
            del self._cache[evict_key]
        self._cache[key] = value

    async def clear_cache(self) -> None:
        """Clear the explanation cache."""
        self._cache.clear()
        logger.info("Explanation cache cleared")


def np_mean(values: list[float]) -> float:
    """Compute mean without numpy dependency."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def np_std(values: list[float]) -> float:
    """Compute standard deviation without numpy dependency."""
    if not values:
        return 0.0
    mean = np_mean(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5
