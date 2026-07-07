from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

import pandas as pd

from regulaforge.ml.domain.enums import ModelType, TaskType
from regulaforge.ml.domain.models import (
    Experiment,
    ExperimentMetric,
    HyperparameterSuggestion,
)

logger = logging.getLogger(__name__)


class HyperparameterOptimizer:
    def __init__(self) -> None:
        self._experiments: dict[UUID, Experiment] = {}

    def optimize(
        self,
        model_type: ModelType,
        x: pd.DataFrame,
        y: pd.Series,
        task_type: TaskType = TaskType.RISK_CLASSIFICATION,
        n_trials: int = 20,
        timeout_seconds: Optional[int] = None,
        cv_folds: int = 3,
        direction: str = "maximize",
        seed: int = 42,
        _early_stopping_rounds: Optional[int] = None,
    ) -> Experiment:
        try:
            import optuna
        except ImportError:
            raise ImportError("optuna is required. Install with: pip install optuna")

        def _objective(trial: optuna.Trial) -> float:
            params = self._sample_params(trial, model_type)
            score = self._cross_val_score(model_type, x, y, params, cv_folds, task_type)
            return score

        study = optuna.create_study(
            direction=direction,
            sampler=optuna.samplers.TPESampler(seed=seed),
        )

        study.optimize(
            _objective,
            n_trials=n_trials,
            timeout=timeout_seconds,
            show_progress_bar=False,
        )

        n_trials = len(study.trials)
        try:
            best_params = study.best_params
            best_score = study.best_value
            status = "completed"
        except ValueError:
            best_params = {}
            best_score = 0.0
            status = "failed"

        exp = Experiment(
            model_type=model_type,
            task_type=task_type,
            hyperparameters=best_params,
            best_score=best_score,
            best_params=best_params,
            n_trials=n_trials,
            status=status,
        )
        if status == "completed":
            for metric_name, value in study.best_trial.user_attrs.items():
                exp.metrics.append(ExperimentMetric(metric_type=type(metric_name), value=value))
        exp.completed_at = pd.Timestamp.now().to_pydatetime()

        self._experiments[exp.id] = exp
        logger.info(
            "HPO completed: model=%s trials=%d best_score=%.4f params=%s",
            model_type.value, len(study.trials), study.best_value, study.best_params,
        )
        return exp

    def suggest(self, params: dict[str, Any]) -> HyperparameterSuggestion:
        return HyperparameterSuggestion(params=params)

    def _sample_params(
        self,
        trial: Any,
        model_type: ModelType,
    ) -> dict[str, Any]:
        if model_type == ModelType.XGBOOST:
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma": trial.suggest_float("gamma", 0, 5),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10, log=True),
            }
        elif model_type == ModelType.CATBOOST:
            return {
                "iterations": trial.suggest_int("iterations", 50, 500, log=True),
                "depth": trial.suggest_int("depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 10, log=True),
                "border_count": trial.suggest_int("border_count", 32, 255),
                "random_strength": trial.suggest_float("random_strength", 1e-8, 10, log=True),
            }
        elif model_type == ModelType.LIGHTGBM:
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10, log=True),
            }
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def _cross_val_score(
        self,
        model_type: ModelType,
        x: pd.DataFrame,
        y: pd.Series,
        params: dict[str, Any],
        cv_folds: int,
        _task_type: TaskType,
    ) -> float:
        from sklearn.metrics import make_scorer, roc_auc_score
        from sklearn.model_selection import cross_val_score

        if model_type == ModelType.XGBOOST:
            import xgboost as xgb
            model = xgb.XGBClassifier(**params, use_label_encoder=False, verbosity=0)
        elif model_type == ModelType.CATBOOST:
            from catboost import CatBoostClassifier
            model = CatBoostClassifier(**params, verbose=False)
        elif model_type == ModelType.LIGHTGBM:
            import lightgbm as lgb
            model = lgb.LGBMClassifier(**params, verbose=-1)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        scorer = make_scorer(roc_auc_score, response_method="predict_proba", multi_class="ovo")
        scores = cross_val_score(model, x, y, cv=min(cv_folds, 5), scoring=scorer)
        return float(scores.mean())

    def get_experiment(self, experiment_id: UUID) -> Optional[Experiment]:
        return self._experiments.get(experiment_id)

    def list_experiments(self) -> list[Experiment]:
        return list(self._experiments.values())
