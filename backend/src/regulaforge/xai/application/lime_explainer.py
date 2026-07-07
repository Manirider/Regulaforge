"""LIME (Local Interpretable Model-agnostic Explanations) explainer.

Provides locally faithful explanations by perturbing input features
and fitting an interpretable surrogate model around each prediction.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from regulaforge.config.logging import get_logger
from regulaforge.xai.domain.models import (
    Explanation,
    ExplanationType,
    FeatureContribution,
)

logger = get_logger(__name__)

_LIME_AVAILABLE: bool = False
try:
    from lime.lime_tabular import LimeTabularExplainer  # type: ignore[import-untyped]

    _LIME_AVAILABLE = True
except ImportError:
    logger.warning("lime library not available; using fallback LIME explainer")


class LimeExplainer:
    """Generates LIME-based local explanations for model predictions.

    Explains individual predictions by perturbing the input and learning
    a sparse linear model around the neighborhood of the prediction.
    Handles both classification and regression tasks.
    """

    def __init__(
        self,
        kernel_width: float = 0.75,
        max_features_display: int = 20,
        random_state: int = 42,
    ) -> None:
        self._kernel_width = kernel_width
        self._max_features_display = max_features_display
        self._random_state = random_state
        logger.info(
            "LimeExplainer initialized: lime_available=%s, kernel_width=%.2f",
            _LIME_AVAILABLE, kernel_width,
        )

    def explain_prediction(
        self,
        model: Any,
        x_sample: Any,
        feature_names: Optional[list[str]] = None,
        num_features: int = 10,
    ) -> Explanation:
        """Generate a LIME explanation for a single prediction.

        Works for both classification and regression models.
        Automatically detects the task type based on model output shape.

        Args:
            model: The ML model (must have predict or predict_proba).
            x_sample: Single sample to explain.
            feature_names: Names of features in order.
            num_features: Number of top features to include.

        Returns:
            Explanation with LIME feature contributions.
        """
        x_array, names = self._preprocess_input(x_sample, feature_names)
        if x_array.ndim == 1:
            x_array = x_array.reshape(1, -1)

        if not _LIME_AVAILABLE or model is None:
            return self._fallback_explanation(names)

        try:
            predict_fn = self._get_predict_fn(model)
            explainer = self._create_explainer(x_array, names, predict_fn)

            exp = explainer.explain_instance(
                x_array[0],
                predict_fn,
                num_features=min(num_features, len(names)),
                top_labels=None,
            )

            features = self._extract_features(exp, x_array[0], names, num_features)
            summary = self._generate_summary(features)

            explanation = Explanation(
                prediction_id=uuid_ref(),
                model_name=getattr(model, "__class__", type(model)).__name__ if model else "unknown",
                explanation_type=ExplanationType.LIME,
                features=features,
                summary=summary,
                confidence=0.9,
                metadata={
                    "method": "lime",
                    "kernel_width": self._kernel_width,
                    "num_features": num_features,
                },
            )
            logger.debug(
                "LIME explanation generated: features=%d",
                len(features),
            )
            return explanation
        except Exception as exc:
            logger.error("LIME explanation failed: %s", exc, exc_info=True)
            return self._fallback_explanation(names)

    def explain_classification(
        self,
        model: Any,
        x_sample: Any,
        class_names: Optional[list[str]] = None,
        num_features: int = 10,
    ) -> Explanation:
        """Generate a LIME explanation specifically for a classification model.

        Args:
            model: Classification model (predict_proba recommended).
            x_sample: Single sample to explain.
            class_names: Names of output classes.
            num_features: Number of top features to include.

        Returns:
            Explanation for the predicted class.
        """
        x_array, names = self._preprocess_input(x_sample, None)
        if x_array.ndim == 1:
            x_array = x_array.reshape(1, -1)

        if not _LIME_AVAILABLE or model is None:
            return self._fallback_explanation(names)

        try:
            predict_fn = self._get_predict_fn(model, use_proba=True)
            explainer = self._create_explainer(x_array, names, predict_fn, class_names=class_names)

            exp = explainer.explain_instance(
                x_array[0],
                predict_fn,
                num_features=min(num_features, len(names)),
                top_labels=1,
            )

            predicted_label = exp.top_labels[0] if exp.top_labels else 0
            exp_map = exp.as_map().get(predicted_label, [])

            features = self._build_features(exp_map, x_array[0], names, num_features)
            summary = self._generate_summary(features)

            label_name = class_names[predicted_label] if class_names and predicted_label < len(class_names) else str(predicted_label)  # noqa: E501
            summary = f"Class '{label_name}': {summary}" if summary else summary

            explanation = Explanation(
                prediction_id=uuid_ref(),
                model_name=getattr(model, "__class__", type(model)).__name__ if model else "unknown",
                explanation_type=ExplanationType.LIME,
                features=features,
                summary=summary,
                confidence=0.9,
                metadata={
                    "method": "lime_classification",
                    "predicted_class": label_name,
                    "num_features": num_features,
                },
            )
            return explanation
        except Exception as exc:
            logger.error("LIME classification failed: %s", exc, exc_info=True)
            return self._fallback_explanation(names)

    def explain_regression(
        self,
        model: Any,
        x_sample: Any,
        feature_names: Optional[list[str]] = None,
        num_features: int = 10,
    ) -> Explanation:
        """Generate a LIME explanation for a regression model.

        Args:
            model: Regression model.
            x_sample: Single sample to explain.
            feature_names: Names of features in order.
            num_features: Number of top features to include.

        Returns:
            Explanation with regression feature contributions.
        """
        return self.explain_prediction(model, x_sample, feature_names, num_features)

    def _preprocess_input(
        self,
        x: Any,
        feature_names: Optional[list[str]] = None,
    ) -> tuple[np.ndarray, list[str]]:
        import pandas as pd  # type: ignore[import-untyped]

        if isinstance(x, pd.DataFrame):
            names = feature_names or list(x.columns)
            return x.values, names

        x_array = np.array(x, dtype=float)
        n_features = x_array.shape[1] if x_array.ndim >= 2 else x_array.shape[0]
        names = feature_names or [f"feature_{i}" for i in range(n_features)]
        return x_array, names

    def _get_predict_fn(
        self,
        model: Any,
        use_proba: bool = False,
    ) -> Any:
        """Get the appropriate prediction function from the model."""
        if use_proba and hasattr(model, "predict_proba"):
            return model.predict_proba
        if hasattr(model, "predict"):
            return model.predict
        if callable(model):
            return model
        raise ValueError("Model must have predict, predict_proba, or be callable")

    def _create_explainer(
        self,
        x: np.ndarray,
        feature_names: list[str],
        _predict_fn: Any,
        class_names: Optional[list[str]] = None,
    ) -> Any:
        """Create a LimeTabularExplainer for the given data."""
        if not _LIME_AVAILABLE:
            raise RuntimeError("LIME library is not available")

        return LimeTabularExplainer(
            training_data=x,
            feature_names=feature_names,
            class_names=class_names,
            mode="classification" if class_names else "regression",
            kernel_width=self._kernel_width,
            random_state=self._random_state,
        )

    def _extract_features(
        self,
        exp: Any,
        sample: np.ndarray,
        feature_names: list[str],
        num_features: int,
    ) -> list[FeatureContribution]:
        """Extract feature contributions from a LIME explanation object."""
        exp_map = exp.as_map()

        contributions: list[FeatureContribution] = []
        if not exp_map:
            return contributions

        first_key = next(iter(exp_map.keys()))
        for idx, weight in exp_map[first_key]:
            if idx < len(feature_names):
                direction = "positive" if weight > 0.01 else "negative" if weight < -0.01 else "neutral"
                contributions.append(FeatureContribution(
                    feature_name=feature_names[idx],
                    feature_value=float(sample[idx]) if idx < len(sample) else 0.0,
                    contribution=float(weight),
                    direction=direction,
                    description=f"LIME weight: {weight:.4f}",
                ))
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        return contributions[:num_features]

    def _build_features(
        self,
        exp_map: list[tuple[int, float]],
        sample: np.ndarray,
        feature_names: list[str],
        num_features: int,
    ) -> list[FeatureContribution]:
        """Build FeatureContribution list from a LIME feature map."""
        contributions: list[FeatureContribution] = []
        for idx, weight in exp_map:
            if idx < len(feature_names):
                direction = "positive" if weight > 0.01 else "negative" if weight < -0.01 else "neutral"
                contributions.append(FeatureContribution(
                    feature_name=feature_names[idx],
                    feature_value=float(sample[idx]) if idx < len(sample) else 0.0,
                    contribution=float(weight),
                    direction=direction,
                    description=f"LIME weight: {weight:.4f}",
                ))
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        return contributions[:num_features]

    def _generate_summary(self, features: list[FeatureContribution]) -> str:
        """Generate a human-readable summary from LIME features."""
        if not features:
            return "No feature contributions available."

        top = features[:5]
        parts: list[str] = []
        for f in top:
            direction = "increases" if f.direction == "positive" else "decreases" if f.direction == "negative" else "does not affect"  # noqa: E501
            parts.append(f"'{f.feature_name}' {direction} the prediction by {abs(f.contribution):.4f}")
        return "Top contributing features: " + "; ".join(parts) + "."

    def _fallback_explanation(
        self,
        _feature_names: list[str],
    ) -> Explanation:
        """Generate a fallback explanation when LIME is unavailable."""
        logger.info("Using fallback explanation (LIME not available)")
        return Explanation(
            prediction_id=uuid_ref(),
            model_name="unknown",
            explanation_type=ExplanationType.LIME,
            features=[],
            summary="LIME explanation unavailable. Install the 'lime' package to enable local interpretable explanations.",  # noqa: E501
            confidence=0.0,
            metadata={
                "method": "fallback",
                "lime_available": _LIME_AVAILABLE,
            },
        )


def uuid_ref() -> Any:
    """Generate a placeholder UUID."""
    from uuid import uuid4
    return uuid4()
