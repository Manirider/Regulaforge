from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.application.evaluator import Evaluator
from regulaforge.ml.application.model_trainer import ModelTrainer
from regulaforge.ml.domain.enums import ModelType


@pytest.fixture
def trained_model():
    trainer = ModelTrainer()
    X = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [2, 3, 4, 5, 6, 7]})
    y = pd.Series([0, 0, 1, 1, 0, 1])
    artifact = trainer.train(ModelType.XGBOOST, X, y)
    return trainer.get_model(artifact.id)


class TestEvaluator:
    def test_evaluate_binary(self, trained_model):
        evaluator = Evaluator()
        X_test = pd.DataFrame({"a": [1, 2], "b": [2, 3]})
        y_test = pd.Series([0, 1])
        result = evaluator.evaluate(trained_model, X_test, y_test)
        assert 0 <= result.accuracy <= 1
        assert 0 <= result.precision <= 1
        assert 0 <= result.recall <= 1
        assert 0 <= result.f1_score <= 1
        assert result.confusion_matrix is not None
        assert result.classification_report is not None

    def test_evaluate_returns_metrics(self, trained_model):
        evaluator = Evaluator()
        X_test = pd.DataFrame({"a": [1, 2], "b": [2, 3]})
        y_test = pd.Series([0, 1])
        result = evaluator.evaluate(trained_model, X_test, y_test)
        assert hasattr(result, "accuracy")
        assert hasattr(result, "precision")

    def test_compare_models(self, trained_model):
        evaluator = Evaluator()
        X_test = pd.DataFrame({"a": [1, 2], "b": [2, 3]})
        y_test = pd.Series([0, 1])
        result1 = evaluator.evaluate(trained_model, X_test, y_test)
        comparison = evaluator.compare_models({"model_a": result1})
        assert "model_a" in comparison
        assert comparison["model_a"]["accuracy"] == result1.accuracy

    def test_get_history(self, trained_model):
        evaluator = Evaluator()
        X_test = pd.DataFrame({"a": [1, 2], "b": [2, 3]})
        y_test = pd.Series([0, 1])
        evaluator.evaluate(trained_model, X_test, y_test)
        assert len(evaluator.get_history()) == 1

    def test_calculate_optimal_threshold(self, trained_model):
        X_val = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 3, 4, 5]})
        y_val = pd.Series([0, 0, 1, 1])
        result = Evaluator.calculate_optimal_threshold(trained_model, X_val, y_val)
        assert "best_threshold" in result
        assert "best_f1" in result
        assert "threshold_curve" in result
        assert len(result["threshold_curve"]) == 81
