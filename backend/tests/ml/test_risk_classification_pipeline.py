from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.domain.enums import ModelType
from regulaforge.ml.pipelines.risk_classification import RiskClassificationPipeline


class TestRiskClassificationPipeline:
    def test_build_feature_set(self):
        pipeline = RiskClassificationPipeline()
        fs = pipeline.build_feature_set()
        assert len(fs.features) == 14
        assert fs.task_type.value == "risk_classification"
        assert fs.target_column == "is_high_risk"

    def test_prepare_features(self):
        pipeline = RiskClassificationPipeline()
        df = pd.DataFrame({
            "amount": [1000, 50000],
            "threshold": [5000, 10000],
            "past_due_days": [0, 90],
            "credit_score": [750, 580],
            "transaction_count": [10, 200],
            "has_collateral": [1, 0],
            "industry_code": ["finance", "tech"],
            "region": ["north", "south"],
        })
        result = pipeline.prepare_features(df)
        assert "amount_to_threshold_ratio" in result.columns
        assert "is_past_due" in result.columns

    def test_run_returns_expected_keys(self):
        pipeline = RiskClassificationPipeline()
        X_train = pd.DataFrame({
            "amount": [1000, 50000, 200, 100000],
            "threshold": [5000, 10000, 5000, 10000],
            "past_due_days": [0, 30, 0, 90],
            "credit_score": [750, 620, 800, 580],
            "transaction_count": [10, 50, 5, 200],
            "has_collateral": [1, 0, 1, 0],
            "industry_code": ["finance", "tech", "health", "finance"],
            "region": ["north", "south", "north", "east"],
        })
        y_train = pd.Series([0, 1, 0, 1])
        X_test = pd.DataFrame({
            "amount": [2000, 75000],
            "threshold": [5000, 10000],
            "past_due_days": [5, 60],
            "credit_score": [700, 600],
            "transaction_count": [20, 100],
            "has_collateral": [1, 0],
            "industry_code": ["tech", "finance"],
            "region": ["west", "south"],
        })
        y_test = pd.Series([0, 1])
        output = pipeline.run(X_train, y_train, X_test, y_test, model_type=ModelType.XGBOOST)
        assert "artifact" in output
        assert "evaluation" in output
        assert "cv_summary" in output
        assert output["artifact"] is not None
        assert output["evaluation"].accuracy > 0

    def test_default_model_type(self):
        pipeline = RiskClassificationPipeline()
        assert pipeline.task_type.value == "risk_classification"
