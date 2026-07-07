from __future__ import annotations

import pandas as pd
import pytest
from regulaforge.ml.application.feature_store import FeatureStore
from regulaforge.ml.domain.enums import FeatureType, TaskType
from regulaforge.ml.domain.models import Feature, FeatureSet


class TestFeatureStore:
    def test_register_and_get_feature_set(self):
        store = FeatureStore()
        fs = FeatureSet(
            name="test_fs",
            features=[Feature(name="a", feature_type=FeatureType.NUMERICAL)],
        )
        fs_id = store.register_feature_set(fs)
        assert store.get_feature_set(fs_id) is fs

    def test_list_feature_sets_empty(self):
        store = FeatureStore()
        assert store.list_feature_sets() == []

    def test_list_feature_sets_by_task_type(self):
        store = FeatureStore()
        fs1 = FeatureSet(name="risk", task_type=TaskType.RISK_CLASSIFICATION)
        fs2 = FeatureSet(name="compliance", task_type=TaskType.COMPLIANCE_PREDICTION)
        store.register_feature_set(fs1)
        store.register_feature_set(fs2)
        assert len(store.list_feature_sets(TaskType.RISK_CLASSIFICATION)) == 1

    def test_compute_features_selects_columns(self):
        store = FeatureStore()
        fs = FeatureSet(
            features=[
                Feature(name="a", feature_type=FeatureType.NUMERICAL),
                Feature(name="b", feature_type=FeatureType.NUMERICAL),
            ],
        )
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        result = store.compute_features(df, fs)
        assert list(result.columns) == ["a", "b"]

    def test_compute_features_missing_non_nullable_raises(self):
        store = FeatureStore()
        fs = FeatureSet(
            features=[Feature(name="missing", feature_type=FeatureType.NUMERICAL, nullable=False)],
        )
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(ValueError, match="Required feature"):
            store.compute_features(df, fs)

    def test_compute_features_missing_nullable_ok(self):
        store = FeatureStore()
        fs = FeatureSet(
            features=[Feature(name="maybe", feature_type=FeatureType.NUMERICAL, nullable=True)],
        )
        df = pd.DataFrame({"a": [1]})
        result = store.compute_features(df, fs)
        assert result["maybe"].isna().all()

    def test_create_risk_features(self):
        df = pd.DataFrame({
            "amount": [1000, 50000],
            "threshold": [5000, 10000],
            "past_due_days": [0, 90],
            "transaction_count": [10, 200],
            "credit_score": [750, 580],
        })
        result = FeatureStore.create_risk_features(df)
        assert "amount_to_threshold_ratio" in result.columns
        assert "past_due_weeks" in result.columns
        assert "is_past_due" in result.columns
        assert "log_past_due_days" in result.columns
        assert "log_transaction_count" in result.columns
        assert "credit_score_binned" in result.columns
        assert list(result["is_past_due"]) == [0, 1]
        assert list(result["credit_score_binned"]) == [4, 1]

    def test_create_compliance_features(self):
        df = pd.DataFrame({
            "regulation_count": [5, 20],
            "days_since_last_review": [30, 365],
            "past_violations": [0, 3],
            "filing_delay_days": [0, 15],
            "audit_score": [95, 65],
        })
        result = FeatureStore.create_compliance_features(df)
        assert "review_frequency_score" in result.columns
        assert "has_violations" in result.columns
        assert "log_violations" in result.columns
        assert "filing_delay_weeks" in result.columns
        assert "is_late_filing" in result.columns
        assert "audit_score_normalized" in result.columns
        assert list(result["has_violations"]) == [0, 1]
        assert list(result["is_late_filing"]) == [0, 1]

    def test_register_transformation(self):
        store = FeatureStore()
        from regulaforge.ml.application.feature_store import FeatureTransformation
        t = FeatureTransformation(name="scale", transform_type="scale", params={"method": "standard"})
        store.register_transformation(t)
        assert t.name in store._transformations
