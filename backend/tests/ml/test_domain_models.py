from __future__ import annotations

from uuid import UUID

from regulaforge.ml.domain.enums import (
    DriftStatus,
    FeatureType,
    MetricType,
    ModelStatus,
    ModelType,
    TaskType,
)
from regulaforge.ml.domain.models import (
    CVResult,
    DriftReport,
    EvaluationResult,
    Experiment,
    Feature,
    FeatureSet,
    HyperparameterSpace,
    LIMEExplanation,
    ModelArtifact,
    MonitorReport,
    RetrainingJob,
    SHAPExplanation,
)


class TestDomainEnums:
    def test_model_type_values(self):
        assert ModelType.XGBOOST.value == "xgboost"
        assert ModelType.CATBOOST.value == "catboost"
        assert ModelType.LIGHTGBM.value == "lightgbm"

    def test_task_type_values(self):
        assert TaskType.RISK_CLASSIFICATION.value == "risk_classification"
        assert TaskType.COMPLIANCE_PREDICTION.value == "compliance_prediction"

    def test_feature_type_values(self):
        assert FeatureType.NUMERICAL.value == "numerical"
        assert FeatureType.CATEGORICAL.value == "categorical"

    def test_model_status_values(self):
        assert ModelStatus.TRAINING.value == "training"
        assert ModelStatus.PRODUCTION.value == "production"

    def test_metric_type_values(self):
        assert MetricType.ACCURACY.value == "accuracy"
        assert MetricType.AUC_ROC.value == "auc_roc"

    def test_drift_status_values(self):
        assert DriftStatus.NO_DRIFT.value == "no_drift"
        assert DriftStatus.DRIFT_DETECTED.value == "drift_detected"


class TestDomainModels:
    def test_feature_creation(self):
        f = Feature(name="amount", feature_type=FeatureType.NUMERICAL, description="Amount")
        assert f.name == "amount"
        assert f.feature_type == FeatureType.NUMERICAL

    def test_feature_set_creation(self):
        fs = FeatureSet(
            name="test",
            features=[Feature(name="a", feature_type=FeatureType.NUMERICAL)],
        )
        assert isinstance(fs.id, UUID)
        assert len(fs.features) == 1

    def test_experiment_creation(self):
        exp = Experiment(name="test_exp", n_trials=10, status="completed")
        assert exp.name == "test_exp"
        assert exp.status == "completed"

    def test_cv_result_creation(self):
        cv = CVResult(fold=0, val_score=0.85, train_score=0.9)
        assert cv.fold == 0
        assert cv.val_score == 0.85

    def test_evaluation_result_creation(self):
        ev = EvaluationResult(accuracy=0.95, f1_score=0.94)
        assert ev.accuracy == 0.95
        assert ev.f1_score == 0.94

    def test_model_artifact_creation(self):
        ma = ModelArtifact(name="test_model", model_type=ModelType.XGBOOST)
        assert isinstance(ma.id, UUID)
        assert ma.status == ModelStatus.STAGING

    def test_shap_explanation_creation(self):
        shap = SHAPExplanation(
            feature_names=["a", "b"],
            feature_importance={"a": 0.6, "b": 0.4},
            top_features=[("a", 0.6), ("b", 0.4)],
        )
        assert len(shap.feature_names) == 2
        assert shap.feature_importance["a"] == 0.6

    def test_lime_explanation_creation(self):
        lime = LIMEExplanation(
            prediction=1.0,
            confidence=0.9,
            top_features=[("a", 0.5)],
        )
        assert lime.prediction == 1.0
        assert lime.confidence == 0.9

    def test_drift_report_creation(self):
        dr = DriftReport(
            feature_name="test",
            drift_score=0.05,
            p_value=0.01,
            status=DriftStatus.WARNING,
        )
        assert dr.feature_name == "test"
        assert dr.status == DriftStatus.WARNING

    def test_monitor_report_creation(self):
        mr = MonitorReport(overall_status=DriftStatus.NO_DRIFT)
        assert mr.overall_status == DriftStatus.NO_DRIFT
        assert not mr.alert_triggered

    def test_retraining_job_creation(self):
        rj = RetrainingJob(trigger_reason="drift_detected")
        assert rj.status == "pending"
        assert rj.trigger_reason == "drift_detected"

    def test_hyperparameter_space_creation(self):
        hs = HyperparameterSpace(
            name="learning_rate",
            param_name="learning_rate",
            param_type="float",
            low=0.01,
            high=0.3,
            log=True,
        )
        assert hs.low == 0.01
        assert hs.high == 0.3
