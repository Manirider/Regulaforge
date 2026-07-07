from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from regulaforge.ml.application.cross_validator import CrossValidator
from regulaforge.ml.application.evaluator import Evaluator
from regulaforge.ml.application.explainer import Explainer
from regulaforge.ml.application.feature_store import FeatureStore
from regulaforge.ml.application.hyperparameter_optimizer import HyperparameterOptimizer
from regulaforge.ml.application.model_registry import ModelRegistry
from regulaforge.ml.application.model_trainer import ModelTrainer
from regulaforge.ml.application.monitor import ModelMonitor
from regulaforge.ml.application.retrainer import Retrainer
from regulaforge.ml.domain.enums import ModelType, TaskType

logger = logging.getLogger(__name__)

_engine: Optional[_MLEngine] = None


class _MLEngine:
    def __init__(self) -> None:
        self.feature_store = FeatureStore()
        self.trainer = ModelTrainer()
        self.optimizer = HyperparameterOptimizer()
        self.cross_validator = CrossValidator()
        self.evaluator = Evaluator()
        self.explainer = Explainer()
        self.registry = ModelRegistry()
        self.monitor = ModelMonitor()
        self.retrainer = Retrainer()


def get_engine() -> _MLEngine:
    global _engine
    if _engine is None:
        _engine = _MLEngine()
    return _engine


router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/train")
async def train_model(
    model_type: str = Query(..., description="xgboost, catboost, lightgbm"),
    task_type: str = Query("risk_classification", description="risk_classification, compliance_prediction"),
) -> dict[str, Any]:
    engine = get_engine()
    x_train = pd.DataFrame({"feature_1": [1, 2, 3], "feature_2": [4, 5, 6]})
    y_train = pd.Series([0, 1, 0])
    artifact = engine.trainer.train(
        model_type=ModelType(model_type),
        x_train=x_train,
        y_train=y_train,
        task_type=TaskType(task_type),
    )
    registered = engine.registry.register(artifact)
    return {
        "artifact_id": str(registered.id),
        "model_type": registered.model_type.value,
        "version": registered.version,
        "status": registered.status.value,
        "training_duration_seconds": registered.training_duration_seconds,
        "feature_importance": registered.feature_importance,
    }


@router.post("/optimize")
async def optimize_hyperparameters(
    model_type: str = Query(..., description="xgboost, catboost, lightgbm"),
    n_trials: int = Query(20, ge=1, le=500),
    task_type: str = Query("risk_classification"),
) -> dict[str, Any]:
    engine = get_engine()
    x = pd.DataFrame({"feature_1": [1, 2, 3, 4, 5], "feature_2": [6, 7, 8, 9, 10]})
    y = pd.Series([0, 1, 0, 1, 0])
    experiment = engine.optimizer.optimize(
        model_type=ModelType(model_type),
        x=x,
        y=y,
        task_type=TaskType(task_type),
        n_trials=n_trials,
    )
    return {
        "experiment_id": str(experiment.id),
        "best_score": experiment.best_score,
        "best_params": experiment.best_params,
        "n_trials": experiment.n_trials,
    }


@router.post("/evaluate")
async def evaluate_model(
    artifact_id: str = Query(...),
) -> dict[str, Any]:
    engine = get_engine()
    model = engine.trainer.get_model(UUID(artifact_id))
    x_test = pd.DataFrame({"feature_1": [1, 2], "feature_2": [3, 4]})
    y_test = pd.Series([0, 1])
    result = engine.evaluator.evaluate(model, x_test, y_test)
    return {
        "accuracy": result.accuracy,
        "precision": result.precision,
        "recall": result.recall,
        "f1_score": result.f1_score,
        "auc_roc": result.auc_roc,
        "confusion_matrix": result.confusion_matrix,
    }


@router.post("/explain/shap")
async def explain_shap(
    artifact_id: str = Query(...),
    sample_size: int = Query(100, le=1000),
) -> dict[str, Any]:
    engine = get_engine()
    model = engine.trainer.get_model(UUID(artifact_id))
    x = pd.DataFrame({"feature_1": [1, 2, 3], "feature_2": [4, 5, 6]})
    explanation = engine.explainer.explain_shap(model, x, sample_size=sample_size)
    return {
        "expected_value": explanation.expected_value,
        "feature_importance": explanation.feature_importance,
        "top_features": explanation.top_features,
    }


@router.post("/explain/lime")
async def explain_lime(
    artifact_id: str = Query(...),
    instance_index: int = Query(0, ge=0),
) -> dict[str, Any]:
    engine = get_engine()
    model = engine.trainer.get_model(UUID(artifact_id))
    x = pd.DataFrame({"feature_1": [1, 2, 3], "feature_2": [4, 5, 6]})
    explanation = engine.explainer.explain_lime(model, x, instance_index=instance_index)
    return {
        "prediction": explanation.prediction,
        "confidence": explanation.confidence,
        "top_features": explanation.top_features,
    }


@router.post("/cv")
async def cross_validate(
    model_type: str = Query(...),
    n_folds: int = Query(5, ge=2, le=20),
) -> dict[str, Any]:
    get_engine()
    x = pd.DataFrame({"feature_1": [1, 2, 3, 4, 5, 6, 7, 8], "feature_2": [9, 10, 11, 12, 13, 14, 15, 16]})
    y = pd.Series([0, 1, 0, 1, 0, 1, 0, 1])
    validator = CrossValidator(n_folds=n_folds)
    results = validator.cross_validate(
        model_type=ModelType(model_type),
        x=x,
        y=y,
    )
    return validator.summary(results)


@router.get("/registry")
async def list_registry(
    model_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> list[dict[str, Any]]:
    engine = get_engine()
    mt = ModelType(model_type) if model_type else None
    from regulaforge.ml.domain.enums import ModelStatus
    st = ModelStatus(status) if status else None
    models = engine.registry.list_models(model_type=mt, status=st)
    return [
        {
            "id": str(m.id),
            "name": m.name,
            "model_type": m.model_type.value,
            "version": m.version,
            "status": m.status.value,
            "metrics": m.metrics,
            "training_date": m.training_date.isoformat(),
        }
        for m in models
    ]


@router.post("/registry/promote")
async def promote_model(model_id: str = Query(...)) -> dict[str, str]:
    engine = get_engine()
    result = engine.registry.promote_to_production(UUID(model_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "promoted", "model_id": model_id, "new_status": result.status.value}


@router.post("/monitor/drift")
async def check_drift(model_id: str = Query(...)) -> dict[str, Any]:
    engine = get_engine()
    x_ref = pd.DataFrame({"feature_1": [1, 2, 3], "feature_2": [4, 5, 6]})
    x_cur = pd.DataFrame({"feature_1": [1.1, 2.2, 3.3], "feature_2": [4.5, 5.5, 6.5]})
    engine.monitor.set_reference_data(x_ref)
    report = engine.monitor.detect_drift(
        model_id=UUID(model_id),
        x_current=x_cur,
    )
    return {
        "report_id": str(report.id),
        "overall_status": report.overall_status.value,
        "data_drift_score": report.data_drift_score,
        "alert_triggered": report.alert_triggered,
        "drifted_features": [
            {
                "feature": r.feature_name,
                "score": r.drift_score,
                "status": r.status.value,
            }
            for r in report.feature_drift_reports
            if r.status.value != "no_drift"
        ],
    }


@router.post("/retrain")
async def retrain_model(
    model_id: str = Query(...),
    trigger_reason: str = Query("api_triggered"),
) -> dict[str, Any]:
    engine = get_engine()
    job = engine.retrainer.create_retraining_job(
        model_id=UUID(model_id),
        trigger_reason=trigger_reason,
    )
    x_train = pd.DataFrame({"feature_1": [1, 2, 3, 4, 5], "feature_2": [6, 7, 8, 9, 10]})
    y = pd.Series([0, 1, 0, 1, 0])
    job = engine.retrainer.execute_retraining(
        job_id=job.id,
        x_train=x_train,
        y_train=y,
        model_type=ModelType.XGBOOST,
        task_type=TaskType.RISK_CLASSIFICATION,
    )
    return {
        "job_id": str(job.id),
        "status": job.status,
        "new_model_id": str(job.new_model_id) if job.new_model_id else None,
        "metrics_before": job.metrics_before,
        "metrics_after": job.metrics_after,
        "error": job.error_message,
    }


@router.get("/models/{model_id}/feature-importance")
async def get_feature_importance(model_id: str) -> dict[str, Any]:
    engine = get_engine()
    artifact = engine.registry.get_model(UUID(model_id))
    if artifact is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "model_id": model_id,
        "feature_importance": artifact.feature_importance or {},
    }
