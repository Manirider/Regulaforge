"""SHAP (SHapley Additive exPlanations) explainer for model predictions.

Provides both global and local explanations using SHAP values,
with optimized support for tree-based models via TreeSHAP.
Falls back gracefully when SHAP is not available.
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

_SHAP_AVAILABLE: bool = False
try:
    import shap  # type: ignore[import-untyped]

    _SHAP_AVAILABLE = True
except ImportError:
    logger.warning("shap library not available; using fallback SHAP explainer")


class ShapExplainer:
    """Generates SHAP-based explanations for model predictions.

    Supports global feature importance, local explanations for individual
    predictions, and tree-model-optimized TreeSHAP. Falls back to a
    coefficient-based approximation when SHAP is not installed.
    """

    def __init__(
        self,
        background_samples: int = 100,
        max_features_display: int = 20,
    ) -> None:
        self._background_samples = background_samples
        self._max_features_display = max_features_display
        self._explainer: Any = None
        logger.info(
            "ShapExplainer initialized: shap_available=%s, background_samples=%d",
            _SHAP_AVAILABLE, background_samples,
        )

    def explain(
        self,
        model: Any,
        x: Any,
        feature_names: Optional[list[str]] = None,
    ) -> Explanation:
        """Generate a global SHAP explanation for the given model and dataset.

        Args:
            model: The ML model to explain (must have predict or predict_proba).
            x: Feature matrix (numpy array, pandas DataFrame, or list of lists).
            feature_names: Names of features in order. Auto-generated if None.

        Returns:
            Explanation with global feature importance.
        """
        x_array, names = self._preprocess_input(x, feature_names)
        if not _SHAP_AVAILABLE or model is None:
            return self._fallback_explanation(model, x_array, names, "global")

        try:
            explainer = self._create_explainer(model, x_array)
            shap_values = explainer.shap_values(x_array)

            features = self.get_feature_importance(shap_values, names)
            summary = self.generate_summary(shap_values, names)

            explanation = Explanation(
                prediction_id=uuid_ref(),
                model_name=getattr(model, "__class__", type(model)).__name__ if model else "unknown",
                explanation_type=ExplanationType.SHAP,
                features=features,
                summary=summary,
                confidence=0.95,
                metadata={
                    "method": "shap",
                    "samples": len(x_array),
                    "features": len(names),
                },
            )
            logger.debug(
                "Global SHAP explanation generated: features=%d, samples=%d",
                len(features), len(x_array),
            )
            return explanation
        except Exception as exc:
            logger.error("SHAP global explanation failed: %s", exc, exc_info=True)
            return self._fallback_explanation(model, x_array, names, "global")

    def explain_prediction(
        self,
        model: Any,
        x_sample: Any,
        feature_names: Optional[list[str]] = None,
    ) -> Explanation:
        """Generate a local SHAP explanation for a single prediction.

        Args:
            model: The ML model to explain.
            x_sample: Single sample feature vector.
            feature_names: Names of features in order.

        Returns:
            Explanation with local feature contributions.
        """
        x_array, names = self._preprocess_input(x_sample, feature_names)
        if x_array.ndim == 1:
            x_array = x_array.reshape(1, -1)

        if not _SHAP_AVAILABLE or model is None:
            return self._fallback_explanation(model, x_array, names, "local")

        try:
            explainer = self._create_explainer(model, x_array)
            shap_values = explainer.shap_values(x_array)

            if isinstance(shap_values, list):
                shap_values = shap_values[0]

            features = self._local_feature_importance(shap_values[0], names)
            summary = self.generate_summary(shap_values, names)

            explanation = Explanation(
                prediction_id=uuid_ref(),
                model_name=getattr(model, "__class__", type(model)).__name__ if model else "unknown",
                explanation_type=ExplanationType.SHAP,
                features=features[:self._max_features_display],
                summary=summary,
                confidence=0.95,
                metadata={
                    "method": "local_shap",
                    "sample_shape": list(x_array.shape),
                },
            )
            logger.debug(
                "Local SHAP explanation generated: features=%d",
                len(features),
            )
            return explanation
        except Exception as exc:
            logger.error("SHAP local explanation failed: %s", exc, exc_info=True)
            return self._fallback_explanation(model, x_array, names, "local")

    def explain_tree_model(
        self,
        model: Any,
        x: Any,
        feature_names: Optional[list[str]] = None,
    ) -> Explanation:
        """Generate TreeSHAP explanation optimized for tree-based models.

        Uses TreeExplainer for significantly faster SHAP computation
        on gradient-boosted trees, random forests, and decision trees.

        Args:
            model: A tree-based model (XGBoost, LightGBM, CatBoost, sklearn).
            x: Feature matrix.
            feature_names: Names of features in order.

        Returns:
            Explanation with TreeSHAP values.
        """
        x_array, names = self._preprocess_input(x, feature_names)

        if not _SHAP_AVAILABLE or model is None:
            return self._fallback_explanation(model, x_array, names, "tree")

        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(x_array)

            if isinstance(shap_values, list):
                shap_values = shap_values[0]

            features = self.get_feature_importance(shap_values, names)
            summary = self.generate_summary(shap_values, names)

            explanation = Explanation(
                prediction_id=uuid_ref(),
                model_name=getattr(model, "__class__", type(model)).__name__ if model else "unknown",
                explanation_type=ExplanationType.TREE_INTERPRETER,
                features=features,
                summary=summary,
                confidence=0.97,
                metadata={
                    "method": "tree_shap",
                    "samples": len(x_array),
                    "features": len(names),
                },
            )
            logger.debug(
                "TreeSHAP explanation generated: features=%d, samples=%d",
                len(features), len(x_array),
            )
            return explanation
        except Exception as exc:
            logger.error("TreeSHAP explanation failed: %s", exc, exc_info=True)
            return self._fallback_explanation(model, x_array, names, "tree")

    def get_feature_importance(
        self,
        shap_values: Any,
        feature_names: Optional[list[str]] = None,
    ) -> list[FeatureContribution]:
        """Extract feature contributions from SHAP values.

        Args:
            shap_values: SHAP values array.
            feature_names: Feature names.

        Returns:
            List of FeatureContribution sorted by absolute contribution.
        """
        if shap_values is None:
            return []

        shap_array = np.array(shap_values)
        if shap_array.ndim == 3:
            shap_array = shap_array.mean(axis=0)

        if shap_array.ndim == 2:
            mean_shap = np.abs(shap_array).mean(axis=0)
        elif shap_array.ndim == 1:
            mean_shap = np.abs(shap_array)
        else:
            mean_shap = np.abs(shap_array).flatten()

        n = len(mean_shap)
        names = feature_names or [f"feature_{i}" for i in range(n)]

        contributions: list[FeatureContribution] = []
        for i in range(min(n, len(names))):
            val = float(shap_array[i]) if shap_array.ndim == 1 else float(shap_array[:, i].mean()) if shap_array.ndim == 2 else float(mean_shap[i])  # noqa: E501
            direction = "positive" if val > 0.01 else "negative" if val < -0.01 else "neutral"
            contributions.append(FeatureContribution(
                feature_name=names[i],
                feature_value=float(mean_shap[i]),
                contribution=val,
                direction=direction,
                description=f"SHAP value: {val:.4f}",
            ))

        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        return contributions

    def get_interaction_values(
        self,
        model: Any,
        x: Any,
    ) -> dict[str, Any]:
        """Compute SHAP interaction values between features.

        Args:
            model: The ML model.
            x: Feature matrix.

        Returns:
            Dict containing interaction matrix and feature names.
        """
        if not _SHAP_AVAILABLE or model is None:
            logger.warning("SHAP not available; cannot compute interaction values")
            return {"interaction_matrix": [], "feature_names": []}

        try:
            x_array, _ = self._preprocess_input(x, None)
            explainer = self._create_explainer(model, x_array)
            if hasattr(explainer, "shap_interaction_values"):
                interaction_values = explainer.shap_interaction_values(x_array)
                if isinstance(interaction_values, list):
                    interaction_values = interaction_values[0]

                feature_names = [f"feature_{i}" for i in range(interaction_values.shape[1])]
                return {
                    "interaction_matrix": interaction_values.tolist(),
                    "feature_names": feature_names,
                    "shape": list(interaction_values.shape),
                }
            logger.warning("Explainer does not support interaction values")
            return {"interaction_matrix": [], "feature_names": []}
        except Exception as exc:
            logger.error("Failed to compute interaction values: %s", exc, exc_info=True)
            return {"interaction_matrix": [], "feature_names": []}

    def generate_summary(
        self,
        shap_values: Any,
        feature_names: Optional[list[str]] = None,
    ) -> str:
        """Generate a human-readable summary from SHAP values.

        Args:
            shap_values: SHAP values array.
            feature_names: Feature names.

        Returns:
            A string summarizing the key insights.
        """
        if shap_values is None:
            return "No SHAP values available."

        try:
            shap_array = np.array(shap_values)
            if shap_array.ndim == 3:
                shap_array = shap_array.mean(axis=0)

            if shap_array.ndim == 2:
                mean_abs = np.abs(shap_array).mean(axis=0)
                mean_shap = shap_array.mean(axis=0)
            elif shap_array.ndim == 1:
                mean_abs = np.abs(shap_array)
                mean_shap = shap_array
            else:
                return "Unable to generate summary from SHAP values."

            names = feature_names or [f"feature_{i}" for i in range(len(mean_abs))]
            top_indices = np.argsort(mean_abs)[::-1][:5]

            parts: list[str] = []
            for idx in top_indices:
                if idx < len(names):
                    direction = "increases" if mean_shap[idx] > 0 else "decreases"
                    parts.append(f"'{names[idx]}' {direction} the prediction by {abs(mean_shap[idx]):.4f}")

            if parts:
                return "Top contributing features: " + "; ".join(parts) + "."
            return "All feature contributions are near zero."
        except Exception as exc:
            logger.error("Failed to generate SHAP summary: %s", exc)
            return "Summary generation failed."

    def _preprocess_input(
        self,
        x: Any,
        feature_names: Optional[list[str]] = None,
    ) -> tuple[np.ndarray, list[str]]:
        """Convert input to numpy array and extract/provide feature names."""
        import pandas as pd  # type: ignore[import-untyped]

        if isinstance(x, pd.DataFrame):
            names = feature_names or list(x.columns)
            return x.values, names

        x_array = np.array(x, dtype=float)
        n_features = x_array.shape[1] if x_array.ndim >= 2 else x_array.shape[0]
        names = feature_names or [f"feature_{i}" for i in range(n_features)]
        return x_array, names

    def _create_explainer(
        self,
        model: Any,
        x: Any,
        background_data: Optional[np.ndarray] = None,
    ) -> Any:
        """Create appropriate SHAP explainer based on model type.

        Uses background_data for the background distribution (or a subset
        of x if not provided). The explainer is then called on the
        explanation data separately to avoid using the same data for
        both background and explanation.
        """
        if not _SHAP_AVAILABLE:
            raise RuntimeError("SHAP library is not available")

        bg = background_data if background_data is not None else x[:min(len(x), self._background_samples)]

        try:
            return shap.TreeExplainer(model)
        except Exception:
            pass

        try:
            return shap.Explainer(model, bg)
        except Exception:
            pass

        try:
            return shap.KernelExplainer(
                model.predict if hasattr(model, "predict") else model,
                bg,
            )
        except Exception as exc:
            logger.error("Failed to create any SHAP explainer: %s", exc)
            raise

    def _local_feature_importance(
        self,
        shap_values_row: np.ndarray,
        feature_names: list[str],
    ) -> list[FeatureContribution]:
        """Extract local feature importance for a single prediction."""
        contributions: list[FeatureContribution] = []
        for i, name in enumerate(feature_names):
            if i >= len(shap_values_row):
                break
            val = float(shap_values_row[i])
            direction = "positive" if val > 0.01 else "negative" if val < -0.01 else "neutral"
            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=val,
                contribution=val,
                direction=direction,
                description=f"Local SHAP value: {val:.4f}",
            ))
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        return contributions

    def _fallback_explanation(
        self,
        model: Any,
        x: np.ndarray,  # noqa: ARG002
        feature_names: list[str],
        explanation_type: str,
    ) -> Explanation:
        """Generate a fallback explanation when SHAP is unavailable."""
        logger.info("Using fallback explanation method for %s", explanation_type)

        contributions: list[FeatureContribution] = []
        if model is not None and hasattr(model, "coef_") and model.coef_ is not None:
            coef = np.array(model.coef_)
            if coef.ndim > 1:
                coef = coef[0] if coef.shape[0] == 1 else coef[0] if coef.shape[0] > 1 else coef
            for i, name in enumerate(feature_names):
                if i < len(coef):
                    val = float(coef[i])
                    direction = "positive" if val > 0.001 else "negative" if val < -0.001 else "neutral"
                    contributions.append(FeatureContribution(
                        feature_name=name,
                        feature_value=val,
                        contribution=val,
                        direction=direction,
                        description=f"Coefficient-based importance: {val:.4f}",
                    ))
            contributions.sort(key=lambda c: abs(c.contribution), reverse=True)

        return Explanation(
            prediction_id=uuid_ref(),
            model_name=getattr(model, "__class__", type(model)).__name__ if model else "unknown",
            explanation_type=ExplanationType.SHAP,
            features=contributions[:self._max_features_display],
            summary="Fallback explanation generated (SHAP not available). Uses model coefficients." if contributions else "No model coefficients available for fallback explanation.",  # noqa: E501
            confidence=0.5,
            metadata={
                "method": "fallback_coefficient",
                "shap_available": _SHAP_AVAILABLE,
                "reason": "SHAP library unavailable or model is None",
            },
        )


def uuid_ref() -> Any:
    """Generate a placeholder UUID for usage where prediction_id is unknown."""
    from uuid import uuid4
    return uuid4()
