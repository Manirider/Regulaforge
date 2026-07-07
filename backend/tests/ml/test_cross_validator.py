from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.application.cross_validator import CrossValidator
from regulaforge.ml.domain.enums import ModelType


class TestCrossValidator:
    @pytest.fixture
    def data(self):
        return {
            "X": pd.DataFrame({
                "a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "b": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            }),
            "y": pd.Series([0, 0, 1, 1, 0, 0, 1, 1, 0, 1]),
        }

    def test_cross_validate_xgboost(self, data):
        validator = CrossValidator(n_folds=3)
        results = validator.cross_validate(ModelType.XGBOOST, data["X"], data["y"])
        assert len(results) == 3
        for r in results:
            assert 0 <= r.val_score <= 1
            assert r.n_train_samples > 0
            assert r.n_val_samples > 0

    def test_cross_validate_with_metrics(self, data):
        validator = CrossValidator(n_folds=3)
        results = validator.cross_validate(
            ModelType.XGBOOST, data["X"], data["y"],
            metrics=["accuracy", "f1"],
        )
        assert "accuracy" in results[0].metrics
        assert "f1" in results[0].metrics

    def test_summary(self, data):
        validator = CrossValidator(n_folds=3)
        results = validator.cross_validate(ModelType.XGBOOST, data["X"], data["y"])
        summary = validator.summary(results)
        assert summary["n_folds"] == 3
        assert "mean_val_score" in summary
        assert "std_val_score" in summary
        assert "fold_scores" in summary

    def test_empty_summary(self):
        validator = CrossValidator()
        assert validator.summary([]) == {}

    def test_cv_catboost(self, data):
        try:
            import catboost
        except ImportError:
            pytest.skip("catboost not installed")
        validator = CrossValidator(n_folds=2)
        results = validator.cross_validate(ModelType.CATBOOST, data["X"], data["y"])
        assert len(results) == 2

    def test_cv_lightgbm(self, data):
        try:
            import lightgbm
        except ImportError:
            pytest.skip("lightgbm not installed")
        validator = CrossValidator(n_folds=2)
        results = validator.cross_validate(ModelType.LIGHTGBM, data["X"], data["y"])
        assert len(results) == 2
