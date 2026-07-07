from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.domain.enums import ModelType, TaskType


class TestHyperparameterOptimizer:
    @pytest.fixture
    def optimizer(self):
        from regulaforge.ml.application.hyperparameter_optimizer import HyperparameterOptimizer
        return HyperparameterOptimizer()

    @pytest.fixture
    def data(self):
        return {
            "X": pd.DataFrame({
                "a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "b": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            }),
            "y": pd.Series([0, 0, 1, 1, 0, 0, 1, 1, 0, 1]),
        }

    def test_optimize_xgboost(self, optimizer, data):
        try:
            import optuna
        except ImportError:
            pytest.skip("optuna not installed")
        experiment = optimizer.optimize(
            ModelType.XGBOOST, data["X"], data["y"],
            n_trials=3, cv_folds=2,
        )
        assert experiment.n_trials == 3
        assert experiment.best_score > 0
        assert len(experiment.best_params) > 0
        assert experiment.status == "completed"

    def test_optimize_catboost(self, optimizer, data):
        try:
            import catboost
            import optuna
        except ImportError:
            pytest.skip("optuna/catboost not installed")
        experiment = optimizer.optimize(
            ModelType.CATBOOST, data["X"], data["y"],
            n_trials=2, cv_folds=2,
        )
        assert experiment.status == "completed"

    def test_optimize_lightgbm(self, optimizer, data):
        try:
            import lightgbm
            import optuna
        except ImportError:
            pytest.skip("optuna/lightgbm not installed")
        experiment = optimizer.optimize(
            ModelType.LIGHTGBM, data["X"], data["y"],
            n_trials=2, cv_folds=2,
        )
        assert experiment.status == "completed"

    def test_suggest_returns_params(self, optimizer):
        suggestion = optimizer.suggest({"a": 1, "b": 2})
        assert suggestion.params == {"a": 1, "b": 2}

    def test_get_experiment(self, optimizer, data):
        try:
            import optuna
        except ImportError:
            pytest.skip("optuna not installed")
        exp = optimizer.optimize(ModelType.XGBOOST, data["X"], data["y"], n_trials=2, cv_folds=2)
        assert optimizer.get_experiment(exp.id) is exp

    def test_list_experiments(self, optimizer, data):
        try:
            import optuna
        except ImportError:
            pytest.skip("optuna not installed")
        optimizer.optimize(ModelType.XGBOOST, data["X"], data["y"], n_trials=2, cv_folds=2)
        assert len(optimizer.list_experiments()) == 1
