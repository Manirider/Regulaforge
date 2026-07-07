"""Visualization data generators for explainable AI.

Produces Plotly-compatible JSON data structures for rendering
interactive explanation visualizations in the user interface.
Supports waterfall plots, force plots, bar charts, dependence
plots, and heatmaps.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from regulaforge.config.logging import get_logger
from regulaforge.xai.domain.models import (
    Explanation,
    FeatureContribution,
)

logger = get_logger(__name__)


class ExplanationVisualizer:
    """Generates visualization-ready data structures from explanations.

    All methods return Plotly-compatible JSON structures that can be
    rendered client-side without requiring Python plotting libraries
    in the frontend.
    """

    def generate_waterfall_plot(
        self,
        explanation: Explanation,
        max_features: int = 15,
    ) -> dict[str, Any]:
        """Generate waterfall chart data showing cumulative contributions.

        Visualizes how each feature adds or subtracts from the base
        prediction to arrive at the final prediction.

        Args:
            explanation: The Explanation to visualize.
            max_features: Maximum number of features to display.

        Returns:
            Plotly-compatible waterfall chart data.
        """
        features = sorted(
            explanation.features,
            key=lambda f: abs(f.contribution),
            reverse=True,
        )[:max_features]

        if not features:
            return {"data": [], "layout": {"title": "No features available"}}

        base_value = 0.0
        feature_names: list[str] = []
        contributions: list[float] = []
        measure: list[str] = []

        cumulative = base_value
        for f in features:
            feature_names.append(f.feature_name)
            contributions.append(f.contribution)
            measure.append("relative")

        total = cumulative + sum(contributions)

        trace = {
            "type": "waterfall",
            "name": explanation.model_name,
            "orientation": "v",
            "x": [*feature_names, "Total"],
            "y": [*contributions, total - base_value],
            "text": [f"{c:+.4f}" for c in contributions] + [f"{total:+.4f}"],
            "textposition": "outside",
            "connector": {"line": {"color": "#6b7280", "dash": "solid"}},
            "increasing": {"marker": {"color": "#ef4444"}},
            "decreasing": {"marker": {"color": "#22c55e"}},
            "totals": {"marker": {"color": "#3b82f6"}},
        }

        layout = {
            "title": f"Feature Contributions ({explanation.explanation_type.value.upper()})",
            "xaxis": {"title": "Features"},
            "yaxis": {"title": "Contribution"},
            "showlegend": False,
            "hovermode": "x",
        }

        return {"data": [trace], "layout": layout}

    def generate_force_plot(
        self,
        explanation: Explanation,
        max_features: int = 15,
    ) -> dict[str, Any]:
        """Generate force plot data showing feature push/pull effects.

        Visualizes features that push the prediction higher (red)
        versus lower (blue) from the base value.

        Args:
            explanation: The Explanation to visualize.
            max_features: Maximum number of features to display.

        Returns:
            Plotly-compatible force plot data.
        """
        features = sorted(
            explanation.features,
            key=lambda f: abs(f.contribution),
            reverse=True,
        )[:max_features]

        if not features:
            return {"data": [], "layout": {"title": "No features available"}}

        feature_names: list[str] = []
        contributions: list[float] = []
        colors: list[str] = []

        for f in features:
            feature_names.append(f.feature_name)
            contributions.append(f.contribution)
            colors.append("#ef4444" if f.direction == "positive" else "#22c55e" if f.direction == "negative" else "#6b7280")  # noqa: E501

        total_effect = sum(contributions)

        trace = {
            "type": "bar",
            "x": contributions,
            "y": feature_names,
            "orientation": "h",
            "marker": {"color": colors},
            "text": [f"{c:+.4f}" for c in contributions],
            "textposition": "outside",
            "name": "Feature Impact",
        }

        layout = {
            "title": f"Force Plot: {explanation.explanation_type.value.upper()} "
                     f"(Total Effect: {total_effect:+.4f})",
            "xaxis": {"title": "Contribution (SHAP value)"},
            "yaxis": {"title": "Features", "autorange": "reversed"},
            "showlegend": False,
            "bargap": 0.15,
            "hovermode": "y",
        }

        return {"data": [trace], "layout": layout}

    def generate_bar_chart(
        self,
        features: list[FeatureContribution],
        title: str = "Feature Importance",
        max_features: int = 20,
    ) -> dict[str, Any]:
        """Generate a bar chart of feature importance (absolute values).

        Args:
            features: List of feature contributions.
            title: Chart title.
            max_features: Maximum number of features to display.

        Returns:
            Plotly-compatible bar chart data.
        """
        sorted_features = sorted(
            features,
            key=lambda f: abs(f.contribution),
            reverse=True,
        )[:max_features]

        if not sorted_features:
            return {"data": [], "layout": {"title": "No features available"}}

        feature_names: list[str] = []
        abs_importance: list[float] = []
        colors: list[str] = []

        for f in sorted_features:
            feature_names.append(f.feature_name)
            abs_importance.append(abs(f.contribution))
            colors.append("#ef4444" if f.direction == "positive" else "#22c55e" if f.direction == "negative" else "#6b7280")  # noqa: E501

        trace = {
            "type": "bar",
            "x": feature_names,
            "y": abs_importance,
            "marker": {"color": colors},
            "text": [f"{v:.4f}" for v in abs_importance],
            "textposition": "outside",
            "name": "|Importance|",
        }

        layout = {
            "title": title,
            "xaxis": {
                "title": "Features",
                "tickangle": -45,
            },
            "yaxis": {"title": "|Importance|"},
            "showlegend": False,
            "bargap": 0.2,
            "hovermode": "x",
        }

        return {"data": [trace], "layout": layout}

    def generate_dependence_plot(
        self,
        feature: str,
        shap_values: Any,
        x: Any,
    ) -> dict[str, Any]:
        """Generate a dependence plot for a single feature.

        Shows how the SHAP value of a feature varies with its value,
        revealing non-linear relationships and interaction effects.

        Args:
            feature: Name or index of the feature to plot.
            shap_values: SHAP values array.
            x: Feature matrix.

        Returns:
            Plotly-compatible scatter plot data.
        """
        try:
            shap_arr = np.array(shap_values, dtype=float)
            x_arr = np.array(x, dtype=float)

            if shap_arr.ndim == 3:
                shap_arr = shap_arr.mean(axis=0)
            if shap_arr.ndim == 2:
                shap_values_1d = shap_arr.mean(axis=1)
            elif shap_arr.ndim == 1:
                shap_values_1d = shap_arr
            else:
                shap_values_1d = shap_arr.flatten()

            if x_arr.ndim == 1:
                x_arr = x_arr.reshape(-1, 1)

            if isinstance(feature, str) and feature.startswith("feature_"):
                feature_idx = int(feature.split("_")[1])
            elif isinstance(feature, int):
                feature_idx = feature
            else:
                try:
                    feature_idx = int(feature)
                except (ValueError, TypeError):
                    feature_idx = 0

            if feature_idx >= x_arr.shape[1]:
                feature_idx = 0

            feature_values = x_arr[:, feature_idx].flatten()

            min_len = min(len(shap_values_1d), len(feature_values))
            sharp = shap_values_1d[:min_len]
            featv = feature_values[:min_len]

            trace = {
                "type": "scatter",
                "mode": "markers",
                "x": featv.tolist(),
                "y": sharp.tolist(),
                "marker": {
                    "color": "#3b82f6",
                    "size": 6,
                    "opacity": 0.7,
                },
                "name": f"Feature: {feature}",
            }

            layout = {
                "title": f"SHAP Dependence Plot: {feature}",
                "xaxis": {"title": f"Feature value ({feature})"},
                "yaxis": {"title": "SHAP value"},
                "showlegend": False,
                "hovermode": "closest",
            }

            return {"data": [trace], "layout": layout}
        except Exception as exc:
            logger.error("Failed to generate dependence plot for %s: %s", feature, exc)
            return {"data": [], "layout": {"title": f"Dependence plot failed: {exc}"}}

    def generate_heatmap(
        self,
        explanation_matrix: list[Explanation],
        max_features: int = 15,
    ) -> dict[str, Any]:
        """Generate a heatmap comparing feature importance across explanations.

        Useful for comparing explanations of multiple predictions or
        multiple models side by side.

        Args:
            explanation_matrix: List of Explanations to compare.
            max_features: Maximum number of features to include.

        Returns:
            Plotly-compatible heatmap data.
        """
        if not explanation_matrix:
            return {"data": [], "layout": {"title": "No explanations to compare"}}

        all_features: dict[str, list[float]] = {}
        for exp in explanation_matrix:
            for f in exp.features:
                if f.feature_name not in all_features:
                    all_features[f.feature_name] = []
                all_features[f.feature_name].append(abs(f.contribution))

        feature_avg = {
            name: np.mean(vals) if vals else 0.0
            for name, vals in all_features.items()
        }
        top_features = sorted(feature_avg, key=feature_avg.get, reverse=True)[:max_features]

        z_matrix: list[list[float]] = []
        for exp in explanation_matrix:
            row: list[float] = []
            feat_map = {f.feature_name: abs(f.contribution) for f in exp.features}
            for feat in top_features:
                row.append(feat_map.get(feat, 0.0))
            z_matrix.append(row)

        trace = {
            "type": "heatmap",
            "z": z_matrix,
            "x": top_features,
            "y": [f"Exp {i+1}" for i in range(len(explanation_matrix))],
            "colorscale": "Reds",
            "hoverongaps": False,
            "colorbar": {"title": "|Importance|"},
        }

        layout = {
            "title": "Feature Importance Heatmap Comparison",
            "xaxis": {
                "title": "Features",
                "tickangle": -45,
            },
            "yaxis": {"title": "Explanations"},
            "hovermode": "closest",
        }

        return {"data": [trace], "layout": layout}

    def generate_summary_plot(
        self,
        explanation: Explanation,
    ) -> dict[str, Any]:
        """Generate a combined summary visualization.

        Produces a bee-swarm-style summary showing the distribution
        of feature contributions across the prediction.

        Args:
            explanation: The Explanation to visualize.

        Returns:
            Plotly-compatible summary plot data.
        """
        features = sorted(
            explanation.features,
            key=lambda f: abs(f.contribution),
            reverse=True,
        )[:20]

        if not features:
            return {"data": [], "layout": {"title": "No features available"}}

        y_positions = list(range(len(features)))
        contributions = [f.contribution for f in features]
        feature_names = [f.feature_name for f in features]
        colors = [
            "#ef4444" if c > 0 else "#22c55e" if c < 0 else "#6b7280"
            for c in contributions
        ]
        sizes = [8 + abs(c) * 20 for c in contributions]

        trace = {
            "type": "scatter",
            "mode": "markers",
            "x": contributions,
            "y": y_positions,
            "marker": {
                "color": colors,
                "size": sizes,
                "opacity": 0.8,
                "line": {"width": 1, "color": "#374151"},
            },
            "text": [
                f"{name}: {c:+.4f}"
                for name, c in zip(feature_names, contributions, strict=False)
            ],
            "hoverinfo": "text",
            "name": "Feature Contributions",
        }

        layout = {
            "title": f"Summary Plot: {explanation.explanation_type.value.upper()}",
            "xaxis": {"title": "Contribution (SHAP value)"},
            "yaxis": {
                "title": "Features",
                "tickvals": y_positions,
                "ticktext": feature_names,
                "autorange": "reversed",
            },
            "showlegend": False,
            "hovermode": "closest",
            "shapes": [
                {
                    "type": "line",
                    "x0": 0,
                    "y0": -0.5,
                    "x1": 0,
                    "y1": len(features) - 0.5,
                    "line": {"color": "#d1d5db", "width": 1, "dash": "dash"},
                }
            ],
        }

        return {"data": [trace], "layout": layout}
