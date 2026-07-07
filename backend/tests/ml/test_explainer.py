from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.application.explainer import Explainer
from regulaforge.ml.application.model_trainer import ModelTrainer
from regulaforge.ml.domain.enums import ModelType


@pytest.fixture
def trained_model():
    trainer = ModelTrainer()
    X = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 3, 4, 5]})
    y = pd.Series([0, 0, 1, 1])
    artifact = trainer.train(ModelType.XGBOOST, X, y)
    return trainer.get_model(artifact.id)


class TestExplainer:
    def test_explain_shap(self, trained_model):
        try:
            import shap
        except ImportError:
            pytest.skip("shap not installed")
        explainer_obj = Explainer()
        X = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        explanation = explainer_obj.explain_shap(trained_model, X)
        assert len(explanation.feature_names) == 2
        assert explanation.expected_value is not None
        assert len(explanation.feature_importance) == 2
        assert len(explanation.top_features) > 0

    def test_explain_shap_with_sample_size(self, trained_model):
        try:
            import shap
        except ImportError:
            pytest.skip("shap not installed")
        explainer_obj = Explainer()
        X = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [6, 7, 8, 9, 10]})
        explanation = explainer_obj.explain_shap(trained_model, X, sample_size=3)
        assert len(explanation.feature_names) == 2

    def test_explain_lime(self, trained_model):
        try:
            import lime
        except ImportError:
            pytest.skip("lime not installed")
        explainer_obj = Explainer()
        X = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        explanation = explainer_obj.explain_lime(trained_model, X, instance_index=0)
        assert explanation.prediction in (0, 1)
        assert 0 <= explanation.confidence <= 1
        assert len(explanation.top_features) > 0

    def test_explain_lime_out_of_bounds_index(self, trained_model):
        try:
            import lime
        except ImportError:
            pytest.skip("lime not installed")
        explainer_obj = Explainer()
        X = pd.DataFrame({"a": [1], "b": [2]})
        explanation = explainer_obj.explain_lime(trained_model, X, instance_index=999)
        assert explanation is not None

    def test_get_latest_shap_none(self):
        explainer_obj = Explainer()
        assert explainer_obj.get_latest_shap() is None

    def test_get_latest_lime_none(self):
        explainer_obj = Explainer()
        assert explainer_obj.get_latest_lime() is None

    def test_get_latest_shap_after_explain(self, trained_model):
        try:
            import shap
        except ImportError:
            pytest.skip("shap not installed")
        explainer_obj = Explainer()
        X = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        explainer_obj.explain_shap(trained_model, X)
        assert explainer_obj.get_latest_shap() is not None
