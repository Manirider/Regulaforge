from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.application.model_trainer import ModelTrainer
from regulaforge.ml.domain.enums import ModelType, TaskType


class TestModelTrainer:
    @pytest.fixture
    def trainer(self):
        return ModelTrainer()

    @pytest.fixture
    def data(self):
        return {
            "X": pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [2, 3, 4, 5, 6, 7]}),
            "y": pd.Series([0, 0, 1, 1, 0, 1]),
        }

    def test_train_xgboost(self, trainer, data):
        artifact = trainer.train(
            ModelType.XGBOOST, data["X"], data["y"],
            task_type=TaskType.RISK_CLASSIFICATION,
        )
        assert artifact.model_type == ModelType.XGBOOST
        assert artifact.task_type == TaskType.RISK_CLASSIFICATION
        assert artifact.feature_importance is not None
        assert len(artifact.feature_importance) == 2
        assert artifact.training_duration_seconds > 0
        model = trainer.get_model(artifact.id)
        preds = trainer.predict(artifact.id, data["X"])
        assert len(preds) == len(data["y"])

    def test_train_catboost(self, trainer, data):
        try:
            import catboost
        except ImportError:
            pytest.skip("catboost not installed")
        artifact = trainer.train(
            ModelType.CATBOOST, data["X"], data["y"],
            task_type=TaskType.RISK_CLASSIFICATION,
        )
        assert artifact.model_type == ModelType.CATBOOST
        model = trainer.get_model(artifact.id)
        preds = trainer.predict(artifact.id, data["X"])
        assert len(preds) == len(data["y"])

    def test_train_lightgbm(self, trainer, data):
        try:
            import lightgbm
        except ImportError:
            pytest.skip("lightgbm not installed")
        artifact = trainer.train(
            ModelType.LIGHTGBM, data["X"], data["y"],
            task_type=TaskType.RISK_CLASSIFICATION,
        )
        assert artifact.model_type == ModelType.LIGHTGBM
        model = trainer.get_model(artifact.id)
        preds = trainer.predict(artifact.id, data["X"])
        assert len(preds) == len(data["y"])

    def test_train_with_validation(self, trainer):
        X = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8], "b": [2, 3, 4, 5, 6, 7, 8, 9]})
        y = pd.Series([0, 0, 1, 1, 0, 0, 1, 1])
        artifact = trainer.train(
            ModelType.XGBOOST, X, y,
            X_val=X.iloc[:2], y_val=y.iloc[:2],
            task_type=TaskType.RISK_CLASSIFICATION,
        )
        assert artifact.model_type == ModelType.XGBOOST

    def test_train_with_custom_params(self, trainer, data):
        params = {"n_estimators": 10, "max_depth": 3}
        artifact = trainer.train(
            ModelType.XGBOOST, data["X"], data["y"],
            hyperparameters=params,
        )
        assert artifact.hyperparameters["n_estimators"] == 10

    def test_predict_proba(self, trainer, data):
        artifact = trainer.train(ModelType.XGBOOST, data["X"], data["y"])
        proba = trainer.predict_proba(artifact.id, data["X"])
        assert proba.shape == (len(data["y"]), 2)
        assert all(0 <= p <= 1 for p in proba[:, 0])

    def test_get_model_not_found(self, trainer):
        from uuid import uuid4
        with pytest.raises(KeyError):
            trainer.get_model(uuid4())

    def test_invalid_model_type(self, trainer, data):
        from regulaforge.ml.domain.enums import ModelType
        with pytest.raises(ValueError):
            trainer.train("invalid", data["X"], data["y"])  # type: ignore[arg-type]

    def test_compliance_prediction_task(self, trainer, data):
        artifact = trainer.train(
            ModelType.XGBOOST, data["X"], data["y"],
            task_type=TaskType.COMPLIANCE_PREDICTION,
        )
        assert artifact.task_type == TaskType.COMPLIANCE_PREDICTION
