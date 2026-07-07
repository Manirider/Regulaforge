from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

from regulaforge.ml.domain.models import LIMEExplanation, SHAPExplanation

logger = logging.getLogger(__name__)


class Explainer:
    def __init__(self) -> None:
        self._shap_explanations: dict[str, Any] = {}
        self._lime_explanations: dict[str, Any] = {}

    def explain_shap(
        self,
        model: Any,
        x: pd.DataFrame,
        sample_size: Optional[int] = None,
        _model_type: Optional[str] = None,
    ) -> SHAPExplanation:
        try:
            import shap
        except ImportError:
            raise ImportError("shap is required. Install with: pip install shap")

        x_sample = x.sample(n=sample_size, random_state=42) if sample_size and len(x) > sample_size else x

        if hasattr(model, "get_booster"):  # noqa: SIM114
            try:
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(x_sample)
            except Exception:
                explainer = shap.Explainer(model, x_sample)
                shap_values = explainer(x_sample).values
        elif str(type(model)).find("catboost") >= 0:
            try:
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(x_sample)
            except Exception:
                explainer = shap.Explainer(model, x_sample)
                shap_values = explainer(x_sample).values
        else:
            explainer = shap.Explainer(model, x_sample)
            shap_values = explainer(x_sample).values

        if isinstance(shap_values, list):
            shap_values = shap_values[0]

        feature_names = list(x_sample.columns)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        feature_importance = dict(zip(feature_names, mean_abs_shap.tolist(), strict=False))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:20]

        explanation = SHAPExplanation(
            feature_names=feature_names,
            shap_values=shap_values.tolist() if hasattr(shap_values, "tolist") else None,
            base_value=float(explainer.expected_value) if hasattr(explainer, "expected_value") else 0.0,
            expected_value=float(np.mean(shap_values)) if isinstance(shap_values, np.ndarray) else 0.0,
            feature_importance=feature_importance,
            top_features=top_features,
        )
        self._shap_explanations["latest"] = explanation
        return explanation

    def explain_lime(
        self,
        model: Any,
        x: pd.DataFrame,
        instance_index: int = 0,
        num_features: int = 10,
    ) -> LIMEExplanation:
        try:
            import lime  # noqa: F401
            from lime.lime_tabular import LimeTabularExplainer
        except ImportError:
            raise ImportError("lime is required. Install with: pip install lime")

        if instance_index >= len(x):
            instance_index = 0

        feature_names = list(x.columns)
        explainer = LimeTabularExplainer(
            training_data=x.values,
            feature_names=feature_names,
            class_names=["negative", "positive"],
            mode="classification",
            random_state=42,
        )

        instance = x.iloc[[instance_index]]
        exp = explainer.explain_instance(
            data_row=instance.values[0],
            predict_fn=model.predict_proba,
            num_features=num_features,
        )

        feature_weights = dict(exp.as_list())
        top_features = sorted(feature_weights.items(), key=lambda x: abs(x[1]), reverse=True)[:num_features]
        prediction = float(model.predict(instance)[0])
        proba = model.predict_proba(instance)[0]
        confidence = float(np.max(proba))

        explanation = LIMEExplanation(
            feature_names=feature_names,
            feature_weights=feature_weights,
            prediction=prediction,
            confidence=confidence,
            top_features=top_features,
            intercept=0.0,
        )
        self._lime_explanations["latest"] = explanation
        return explanation

    def get_latest_shap(self) -> Optional[SHAPExplanation]:
        return self._shap_explanations.get("latest")

    def get_latest_lime(self) -> Optional[LIMEExplanation]:
        return self._lime_explanations.get("latest")
