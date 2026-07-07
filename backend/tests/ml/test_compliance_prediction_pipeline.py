from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.domain.enums import ModelType
from regulaforge.ml.pipelines.compliance_prediction import CompliancePredictionPipeline


class TestCompliancePredictionPipeline:
    def test_build_feature_set(self):
        pipeline = CompliancePredictionPipeline()
        fs = pipeline.build_feature_set()
        assert len(fs.features) == 14
        assert fs.task_type.value == "compliance_prediction"
        assert fs.target_column == "is_compliant"

    def test_prepare_features(self):
        pipeline = CompliancePredictionPipeline()
        df = pd.DataFrame({
            "regulation_count": [5, 20],
            "days_since_last_review": [30, 365],
            "past_violations": [0, 3],
            "filing_delay_days": [0, 15],
            "audit_score": [95, 65],
            "entity_size": ["small", "large"],
            "sector": ["finance", "banking"],
            "jurisdiction": ["rbi", "sebi"],
        })
        result = pipeline.prepare_features(df)
        assert "review_frequency_score" in result.columns
        assert "has_violations" in result.columns

    def test_run_returns_expected_keys(self):
        pipeline = CompliancePredictionPipeline()
        X_train = pd.DataFrame({
            "regulation_count": [5, 20, 3, 15],
            "days_since_last_review": [30, 200, 10, 365],
            "past_violations": [0, 3, 0, 1],
            "filing_delay_days": [0, 15, 0, 5],
            "audit_score": [95, 65, 90, 75],
            "entity_size": ["small", "large", "small", "medium"],
            "sector": ["finance", "banking", "insurance", "finance"],
            "jurisdiction": ["rbi", "sebi", "irdai", "rbi"],
        })
        y_train = pd.Series([1, 0, 1, 1])
        X_test = pd.DataFrame({
            "regulation_count": [8, 25],
            "days_since_last_review": [60, 300],
            "past_violations": [0, 5],
            "filing_delay_days": [2, 30],
            "audit_score": [88, 55],
            "entity_size": ["medium", "large"],
            "sector": ["insurance", "banking"],
            "jurisdiction": ["irdai", "sebi"],
        })
        y_test = pd.Series([1, 0])
        output = pipeline.run(X_train, y_train, X_test, y_test, model_type=ModelType.XGBOOST)
        assert "artifact" in output
        assert "evaluation" in output
        assert "cv_summary" in output

    def test_default_model_type(self):
        pipeline = CompliancePredictionPipeline()
        assert pipeline.task_type.value == "compliance_prediction"
