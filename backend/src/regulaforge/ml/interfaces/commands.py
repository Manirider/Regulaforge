from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from regulaforge.ml.application.cross_validator import CrossValidator
from regulaforge.ml.application.evaluator import Evaluator
from regulaforge.ml.application.explainer import Explainer
from regulaforge.ml.application.feature_store import FeatureStore
from regulaforge.ml.application.hyperparameter_optimizer import HyperparameterOptimizer
from regulaforge.ml.application.model_registry import ModelRegistry
from regulaforge.ml.application.model_trainer import ModelTrainer
from regulaforge.ml.application.monitor import ModelMonitor
from regulaforge.ml.application.retrainer import Retrainer
from regulaforge.ml.domain.enums import ModelStatus, ModelType, TaskType

logger = logging.getLogger(__name__)


def create_ml_cli(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "ml",
        help="ML pipeline operations: train, optimize, evaluate, explain, monitor, retrain",
    )
    parser.set_defaults(subsystem="ml")
    sub = parser.add_subparsers(dest="ml_command")

    train_parser = sub.add_parser("train", help="Train a model")
    train_parser.add_argument("--model-type", required=True, choices=["xgboost", "catboost", "lightgbm"])
    train_parser.add_argument("--task-type", default="risk_classification",
                              choices=["risk_classification", "compliance_prediction"])
    train_parser.add_argument("--output", choices=["text", "json"], default="text")

    optimize_parser = sub.add_parser("optimize", help="Run hyperparameter optimization")
    optimize_parser.add_argument("--model-type", required=True, choices=["xgboost", "catboost", "lightgbm"])
    optimize_parser.add_argument("--n-trials", type=int, default=20)
    optimize_parser.add_argument("--output", choices=["text", "json"], default="text")

    evaluate_parser = sub.add_parser("evaluate", help="Evaluate a model")
    evaluate_parser.add_argument("--model-id", required=True)
    evaluate_parser.add_argument("--output", choices=["text", "json"], default="text")

    explain_parser = sub.add_parser("explain", help="Explain a model prediction")
    explain_parser.add_argument("--model-id", required=True)
    explain_parser.add_argument("--method", default="shap", choices=["shap", "lime"])
    explain_parser.add_argument("--output", choices=["text", "json"], default="text")

    cv_parser = sub.add_parser("cv", help="Run cross-validation")
    cv_parser.add_argument("--model-type", required=True, choices=["xgboost", "catboost", "lightgbm"])
    cv_parser.add_argument("--folds", type=int, default=5)

    registry_parser = sub.add_parser("registry", help="List model registry")
    registry_parser.add_argument("--model-type", default=None, choices=["xgboost", "catboost", "lightgbm"])
    registry_parser.add_argument("--status", default=None)

    promote_parser = sub.add_parser("promote", help="Promote model to production")
    promote_parser.add_argument("--model-id", required=True)

    monitor_parser = sub.add_parser("monitor", help="Check model drift")
    monitor_parser.add_argument("--model-id", required=True)

    retrain_parser = sub.add_parser("retrain", help="Retrain a model")
    retrain_parser.add_argument("--model-id", required=True)
    retrain_parser.add_argument("--reason", default="cli_triggered")

    sub.add_parser("features", help="List registered feature sets")


def _get_engine() -> dict[str, Any]:
    return {
        "feature_store": FeatureStore(),
        "trainer": ModelTrainer(),
        "optimizer": HyperparameterOptimizer(),
        "evaluator": Evaluator(),
        "explainer": Explainer(),
        "registry": ModelRegistry(),
        "monitor": ModelMonitor(),
        "retrainer": Retrainer(),
    }


async def handle_ml_command(args: Any) -> None:
    cmd = getattr(args, "ml_command", None)
    if cmd is None:
        return

    engine = _get_engine()
    output = getattr(args, "output", "text")

    if cmd == "train":
        x_train = pd.DataFrame({"feature_1": [1, 2, 3, 4, 5], "feature_2": [6, 7, 8, 9, 10]})
        y = pd.Series([0, 1, 0, 1, 0])
        artifact = engine["trainer"].train(
            model_type=ModelType(args.model_type),
            x_train=x_train,
            y_train=y,
            task_type=TaskType(args.task_type),
        )
        registered = engine["registry"].register(artifact)
        result = {
            "artifact_id": str(registered.id),
            "model_type": registered.model_type.value,
            "version": registered.version,
            "status": registered.status.value,
            "training_duration_seconds": registered.training_duration_seconds,
        }
        if output == "json":
            pass
        else:
            pass

    elif cmd == "optimize":
        x = pd.DataFrame({"feature_1": [1, 2, 3, 4, 5], "feature_2": [6, 7, 8, 9, 10]})
        y = pd.Series([0, 1, 0, 1, 0])
        experiment = engine["optimizer"].optimize(
            model_type=ModelType(args.model_type),
            x=x,
            y=y,
            n_trials=args.n_trials,
        )
        result = {
            "experiment_id": str(experiment.id),
            "best_score": experiment.best_score,
            "best_params": experiment.best_params,
            "n_trials": experiment.n_trials,
        }
        if output == "json":
            pass
        else:
            pass

    elif cmd == "evaluate":
        from uuid import UUID
        model = engine["trainer"].get_model(UUID(args.model_id))
        x_test = pd.DataFrame({"feature_1": [1, 2], "feature_2": [3, 4]})
        y_test = pd.Series([0, 1])
        result = engine["evaluator"].evaluate(model, x_test, y_test)
        result_dict = {
            "accuracy": result.accuracy,
            "precision": result.precision,
            "recall": result.recall,
            "f1": result.f1_score,
            "auc_roc": result.auc_roc,
        }
        if output == "json":
            pass
        else:
            for _k, _v in result_dict.items():
                pass

    elif cmd == "explain":
        from uuid import UUID
        model = engine["trainer"].get_model(UUID(args.model_id))
        x = pd.DataFrame({"feature_1": [1, 2, 3], "feature_2": [4, 5, 6]})
        if args.method == "shap":
            explanation = engine["explainer"].explain_shap(model, x)
            result = {
                "expected_value": explanation.expected_value,
                "top_features": explanation.top_features[:10],
            }
        else:
            explanation = engine["explainer"].explain_lime(model, x)
            result = {
                "prediction": explanation.prediction,
                "confidence": explanation.confidence,
                "top_features": explanation.top_features[:10],
            }
        if output == "json":
            pass
        else:
            for _feat, _imp in result["top_features"]:
                pass

    elif cmd == "cv":
        x = pd.DataFrame({
            "feature_1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "feature_2": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        })
        y = pd.Series([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
        validator = CrossValidator(n_folds=args.folds)
        results = validator.cross_validate(
            model_type=ModelType(args.model_type), x=x, y=y,
        )
        validator.summary(results)

    elif cmd == "registry":
        mt = ModelType(args.model_type) if args.model_type else None
        st = ModelStatus(args.status) if args.status else None
        engine["registry"].list_models(model_type=mt, status=st)

    elif cmd == "promote":
        from uuid import UUID
        result = engine["registry"].promote_to_production(UUID(args.model_id))
        if result:
            pass
        else:
            pass

    elif cmd == "monitor":
        from uuid import UUID
        x_ref = pd.DataFrame({"feature_1": [1, 2, 3], "feature_2": [4, 5, 6]})
        x_cur = pd.DataFrame({"feature_1": [1.1, 2.2, 3.3], "feature_2": [4.5, 5.5, 6.5]})
        engine["monitor"].set_reference_data(x_ref)
        engine["monitor"].detect_drift(
            model_id=UUID(args.model_id), x_current=x_cur,
        )

    elif cmd == "retrain":
        from uuid import UUID
        job = engine["retrainer"].create_retraining_job(
            model_id=UUID(args.model_id), trigger_reason=args.reason,
        )
        x_train = pd.DataFrame({"feature_1": [1, 2, 3, 4, 5], "feature_2": [6, 7, 8, 9, 10]})
        y = pd.Series([0, 1, 0, 1, 0])
        job = engine["retrainer"].execute_retraining(
            job_id=job.id, x_train=x_train, y_train=y,
            model_type=ModelType.XGBOOST, task_type=TaskType.RISK_CLASSIFICATION,
        )

    elif cmd == "features":
        engine["feature_store"].list_feature_sets()
