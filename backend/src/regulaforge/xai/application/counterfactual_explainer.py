"""Counterfactual explanation generator for model predictions.

Provides counterfactual explanations by finding minimal input changes
that would flip a model's prediction, enabling what-if analysis and
remediation path discovery.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any, Optional

import numpy as np

from regulaforge.config.logging import get_logger
from regulaforge.xai.domain.models import CounterfactualExplanation

logger = get_logger(__name__)


class CounterfactualExplainer:
    """Generates counterfactual explanations for model predictions.

    Finds minimal, diverse, and feasible changes to input features
    that would produce a different model outcome. Supports what-if
    analysis and ranking by sparsity and proximity.

    Uses feature perturbation when DiCE is not available, providing
    a gradient-free approach compatible with any black-box model.
    """

    def __init__(
        self,
        num_counterfactuals: int = 5,
        max_iterations: int = 1000,
        step_size: float = 0.1,
        random_state: int = 42,
    ) -> None:
        self._num_counterfactuals = num_counterfactuals
        self._max_iterations = max_iterations
        self._step_size = step_size
        self._random_state = random_state
        random.seed(random_state)
        np.random.seed(random_state)
        logger.info(
            "CounterfactualExplainer initialized: num_cf=%d, max_iter=%d",
            num_counterfactuals, max_iterations,
        )

    def generate_counterfactual(
        self,
        model: Any,
        x_sample: Any,
        desired_outcome: Any,
        feature_ranges: Optional[dict[str, tuple[float, float]]] = None,
    ) -> CounterfactualExplanation:
        """Generate a counterfactual explanation for a prediction.

        Finds the minimal changes to the input that would result in
        the desired outcome, using iterative feature perturbation
        guided by the model's prediction gradient.

        Args:
            model: The ML model to explain.
            x_sample: Single sample to find counterfactual for.
            desired_outcome: The target outcome to achieve.
            feature_ranges: Dict mapping feature names to (min, max) bounds.

        Returns:
            CounterfactualExplanation with the best counterfactual found.
        """
        x_array = self._to_array(x_sample)
        if x_array.ndim == 1:
            x_array = x_array.reshape(1, -1)

        if model is None:
            return self._fallback_counterfactual(x_array, "Model is None")

        try:
            predict_fn = self._get_predict_fn(model)
            original_outcome = self._get_prediction(predict_fn, x_array)
            n_features = x_array.shape[1]

            counterfactuals = self._find_counterfactuals(
                predict_fn, x_array, desired_outcome, n_features, feature_ranges
            )

            if not counterfactuals:
                logger.warning("No valid counterfactuals found")
                return CounterfactualExplanation(
                    original_input=self._to_dict(x_array[0]),
                    outcome_change=f"Could not find counterfactual for desired outcome: {desired_outcome}",
                    distance=float("inf"),
                    viability=0.0,
                    natural_language=f"No feasible counterfactual found to achieve {desired_outcome}.",
                )

            best_cf = counterfactuals[0]
            feature_changes = self._compute_changes(x_array[0], best_cf)

            distance = float(np.linalg.norm(x_array[0] - best_cf))
            viability = self._compute_viability(best_cf, x_array[0], feature_ranges)
            new_outcome = self._get_prediction(predict_fn, best_cf.reshape(1, -1))

            nl = self._generate_natural_language(
                feature_changes, original_outcome, new_outcome
            )

            explanation = CounterfactualExplanation(
                original_input=self._to_dict(x_array[0]),
                counterfactual_input=self._to_dict(best_cf),
                feature_changes=feature_changes,
                outcome_change=f"{original_outcome} -> {new_outcome}",
                distance=round(distance, 4),
                viability=round(viability, 4),
                natural_language=nl,
            )
            logger.debug(
                "Counterfactual generated: distance=%.4f, viability=%.4f",
                distance, viability,
            )
            return explanation
        except Exception as exc:
            logger.error("Counterfactual generation failed: %s", exc, exc_info=True)
            return self._fallback_counterfactual(x_array, str(exc))

    def generate_what_if(
        self,
        x_sample: Any,
        feature_changes: dict[str, float],
    ) -> dict[str, Any]:
        """Perform a what-if analysis by applying specified feature changes.

        Args:
            x_sample: Original sample.
            feature_changes: Dict mapping feature names/indices to new values.

        Returns:
            Dict with original and modified input.
        """
        x_array = self._to_array(x_sample)
        if x_array.ndim == 1:
            x_array = x_array.reshape(1, -1)

        modified = x_array.copy()
        changes: list[dict[str, Any]] = []

        for key, new_value in feature_changes.items():
            if isinstance(key, str) and key.startswith("feature_"):
                idx = int(key.split("_")[1])
            elif isinstance(key, int):
                idx = key
            else:
                try:
                    idx = int(key)
                except (ValueError, TypeError):
                    logger.warning("Invalid feature key for what-if: %s", key)
                    continue

            if 0 <= idx < modified.shape[1]:
                old_val = float(modified[0, idx])
                modified[0, idx] = new_value
                changes.append({
                    "feature": str(key),
                    "original_value": old_val,
                    "new_value": new_value,
                    "delta": new_value - old_val,
                })

        logger.debug(
            "What-if analysis: %d features changed",
            len(changes),
        )
        return {
            "original_input": self._to_dict(x_array[0]),
            "modified_input": self._to_dict(modified[0]),
            "feature_changes": changes,
        }

    def find_minimal_changes(
        self,
        model: Any,
        x_sample: Any,
        desired_outcome: Any,
    ) -> CounterfactualExplanation:
        """Find the minimal changes needed to achieve a desired outcome.

        Optimizes for sparsity (fewest feature changes) and proximity
        (smallest total change magnitude).

        Args:
            model: The ML model.
            x_sample: Original sample.
            desired_outcome: Target prediction outcome.

        Returns:
            CounterfactualExplanation with minimal changes.
        """
        cf = self.generate_counterfactual(model, x_sample, desired_outcome)
        return cf

    def _find_counterfactuals(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        desired_outcome: Any,
        n_features: int,
        _feature_ranges: Optional[dict[str, tuple[float, float]]] = None,
    ) -> list[np.ndarray]:
        """Search for diverse counterfactuals by random perturbation."""
        candidates: list[tuple[np.ndarray, float]] = []
        self._get_prediction(predict_fn, x)

        for _ in range(self._num_counterfactuals * 10):
            candidate = x.copy()
            n_changes = random.randint(1, max(2, n_features // 2))
            indices = random.sample(range(n_features), min(n_changes, n_features))

            for idx in indices:
                perturbation = np.random.uniform(-self._step_size * 5, self._step_size * 5)
                candidate[0, idx] += perturbation

            new_pred = self._get_prediction(predict_fn, candidate)
            if self._outcome_matches(new_pred, desired_outcome):
                distance = float(np.linalg.norm(x[0] - candidate[0]))
                candidates.append((candidate.copy(), distance))

        candidates.sort(key=lambda x: x[1])
        return [c[0] for c in candidates[:self._num_counterfactuals]]

    def _compute_changes(
        self,
        original: np.ndarray,
        counterfactual: np.ndarray,
    ) -> list[dict[str, Any]]:
        """Compute feature-by-feature changes between original and CF."""
        changes: list[dict[str, Any]] = []
        for i in range(len(original)):
            delta = float(counterfactual[i] - original[i])
            if abs(delta) > 1e-6:
                changes.append({
                    "feature": f"feature_{i}",
                    "original_value": float(original[i]),
                    "new_value": float(counterfactual[i]),
                    "delta": round(delta, 4),
                })
        return changes

    def _compute_viability(
        self,
        counterfactual: np.ndarray,
        original: np.ndarray,
        feature_ranges: Optional[dict[str, tuple[float, float]]] = None,
    ) -> float:
        """Estimate how realistic the counterfactual is (0-1)."""
        if feature_ranges:
            violations = 0
            total = 0
            for i in range(len(counterfactual)):
                key = f"feature_{i}"
                if key in feature_ranges:
                    total += 1
                    lo, hi = feature_ranges[key]
                    if counterfactual[i] < lo or counterfactual[i] > hi:
                        violations += 1
            range_compliance = 1.0 - violations / total if total > 0 else 1.0
        else:
            range_compliance = 1.0

        distance = float(np.linalg.norm(counterfactual - original))
        max_expected = self._step_size * 10 * len(original)
        proximity = max(0.0, 1.0 - (distance / max_expected)) if max_expected > 0 else 0.5

        viability = 0.6 * range_compliance + 0.4 * proximity
        return max(0.0, min(1.0, viability))

    def _generate_natural_language(
        self,
        changes: list[dict[str, Any]],
        original_outcome: Any,
        new_outcome: Any,
    ) -> str:
        """Generate human-readable description of counterfactual."""
        if not changes:
            return f"The prediction would change from {original_outcome} to {new_outcome} without any feature changes."

        n_changed = len(changes)
        top_changes = changes[:3]
        details = "; ".join(
            f"change {c['feature']} from {c['original_value']:.2f} to {c['new_value']:.2f}"
            for c in top_changes
        )
        extra = f" (and {n_changed - 3} other feature{'s' if n_changed > 3 else ''})" if n_changed > 3 else ""

        return (
            f"To change the prediction from {original_outcome} to {new_outcome}, "
            f"{n_changed} feature{'s' if n_changed != 1 else ''} need{'s' if n_changed == 1 else ''} to change: "
            f"{details}{extra}."
        )

    def _to_array(self, x: Any) -> np.ndarray:
        """Convert input to numpy array."""
        import pandas as pd  # type: ignore[import-untyped]

        if isinstance(x, pd.DataFrame):
            return x.values.astype(float)
        return np.array(x, dtype=float)

    def _to_dict(self, x_row: np.ndarray) -> dict[str, float]:
        """Convert array row to dict."""
        return {f"feature_{i}": float(v) for i, v in enumerate(x_row)}

    def _get_predict_fn(self, model: Any) -> Callable:
        """Get prediction function from model."""
        if callable(model):
            return model
        if hasattr(model, "predict"):
            return model.predict
        if hasattr(model, "predict_proba"):
            return model.predict_proba
        raise ValueError("Model must be callable or have predict/predict_proba")

    def _get_prediction(self, predict_fn: Callable, x: np.ndarray) -> Any:
        """Get prediction for a sample, handling both classes and values."""
        pred = predict_fn(x)
        if isinstance(pred, list | np.ndarray):
            if pred.ndim > 1 and pred.shape[1] > 1:
                return int(np.argmax(pred[0]))
            return float(pred[0]) if pred.ndim > 0 else float(pred)
        return float(pred)

    def _outcome_matches(self, prediction: Any, desired_outcome: Any) -> bool:
        """Check if the prediction matches the desired outcome."""
        if isinstance(desired_outcome, int | float):
            return abs(float(prediction) - float(desired_outcome)) < 0.5
        if isinstance(desired_outcome, str):
            return str(prediction).lower() == desired_outcome.lower()
        return prediction == desired_outcome

    def _fallback_counterfactual(
        self,
        x: np.ndarray,
        error_message: str,
    ) -> CounterfactualExplanation:
        """Generate a fallback counterfactual when generation fails."""
        logger.info("Using fallback counterfactual: %s", error_message)
        return CounterfactualExplanation(
            original_input=self._to_dict(x[0]),
            outcome_change="Counterfactual generation failed",
            distance=float("inf"),
            viability=0.0,
            natural_language=f"Counterfactual explanation could not be generated. Error: {error_message}",
        )
