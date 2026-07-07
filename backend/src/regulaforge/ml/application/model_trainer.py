from __future__ import annotations

import logging
import time
from typing import Any, Optional
from uuid import UUID

import numpy as np
import pandas as pd

from regulaforge.ml.domain.enums import ModelStatus, ModelType, TaskType
from regulaforge.ml.domain.models import ModelArtifact

logger = logging.getLogger(__name__)


def _convert_categorical(df: pd.DataFrame) -> pd.DataFrame:
    object_cols = df.select_dtypes(include=["object"]).columns
    if len(object_cols) > 0:
        df = df.copy()
        df[object_cols] = df[object_cols].astype("category")
    return df


class ModelTrainer:
    def __init__(self) -> None:
        self._trained_models: dict[UUID, Any] = {}

    def train(
        self,
        model_type: ModelType,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        hyperparameters: Optional[dict[str, Any]] = None,
        task_type: TaskType = TaskType.RISK_CLASSIFICATION,
        **kwargs: Any,
    ) -> ModelArtifact:
        params = dict(hyperparameters or {})

        if model_type == ModelType.XGBOOST:
            return self._train_xgboost(x_train, y_train, x_val, y_val, params, task_type, **kwargs)
        elif model_type == ModelType.CATBOOST:
            return self._train_catboost(x_train, y_train, x_val, y_val, params, task_type, **kwargs)
        elif model_type == ModelType.LIGHTGBM:
            return self._train_lightgbm(x_train, y_train, x_val, y_val, params, task_type, **kwargs)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def _train_xgboost(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        params: dict[str, Any],
        task_type: TaskType,
        **kwargs: Any,
    ) -> ModelArtifact:
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost is required. Install with: pip install xgboost")

        objective = "binary:logistic" if task_type == TaskType.RISK_CLASSIFICATION else "binary:logistic"
        n_classes = kwargs.get("n_classes", 2)
        if n_classes > 2:
            objective = "multi:softprob"

        default_params = {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 1,
            "gamma": 0,
            "reg_alpha": 0,
            "reg_lambda": 1,
            "random_state": 42,
            "objective": objective,
        }
        if n_classes > 2:
            default_params["num_class"] = n_classes

        default_params.update(params)
        start = time.time()

        x_train = _convert_categorical(x_train)
        if x_val is not None:
            x_val = _convert_categorical(x_val)

        eval_set = [(x_train, y_train)]
        if x_val is not None and y_val is not None:
            eval_set.append((x_val, y_val))

        default_params.setdefault("enable_categorical", True)
        model = xgb.XGBClassifier(**default_params)
        model.fit(
            x_train, y_train,
            eval_set=eval_set,
            verbose=False,
        )

        duration = time.time() - start
        feature_importance = dict(
            zip(
                x_train.columns,
                model.feature_importances_.tolist(), strict=False,
            )
        ) if hasattr(model, "feature_importances_") else None

        artifact = ModelArtifact(
            model_type=ModelType.XGBOOST,
            task_type=task_type,
            status=ModelStatus.TRAINING,
            hyperparameters=default_params,
            feature_importance=feature_importance,
            training_duration_seconds=duration,
        )
        self._trained_models[artifact.id] = model
        return artifact

    def _train_catboost(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        params: dict[str, Any],
        task_type: TaskType,
        **kwargs: Any,
    ) -> ModelArtifact:
        try:
            from catboost import CatBoostClassifier
        except ImportError:
            raise ImportError("catboost is required. Install with: pip install catboost")

        kwargs.get("n_classes", 2)
        default_params = {
            "iterations": 100,
            "depth": 6,
            "learning_rate": 0.1,
            "l2_leaf_reg": 3,
            "border_count": 128,
            "random_seed": 42,
            "verbose": False,
        }
        default_params.update(params)

        start = time.time()
        model = CatBoostClassifier(**default_params)
        model.fit(
            x_train, y_train,
            eval_set=(x_val, y_val) if x_val is not None and y_val is not None else None,
            verbose=False,
        )

        duration = time.time() - start
        feat_imp = model.get_feature_importance()
        feature_importance = dict(zip(x_train.columns, feat_imp.tolist(), strict=False))

        artifact = ModelArtifact(
            model_type=ModelType.CATBOOST,
            task_type=task_type,
            status=ModelStatus.TRAINING,
            hyperparameters=default_params,
            feature_importance=feature_importance,
            training_duration_seconds=duration,
        )
        self._trained_models[artifact.id] = model
        return artifact

    def _train_lightgbm(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        params: dict[str, Any],
        task_type: TaskType,
        **kwargs: Any,
    ) -> ModelArtifact:
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("lightgbm is required. Install with: pip install lightgbm")

        n_classes = kwargs.get("n_classes", 2)
        objective = "binary" if n_classes == 2 else "multiclass"

        default_params = {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_samples": 20,
            "reg_alpha": 0,
            "reg_lambda": 0,
            "random_state": 42,
            "objective": objective,
            "verbose": -1,
        }
        if n_classes > 2:
            default_params["num_class"] = n_classes
        default_params.update(params)

        start = time.time()
        model = lgb.LGBMClassifier(**default_params)
        model.fit(
            x_train, y_train,
            eval_set=[(x_val, y_val)] if x_val is not None and y_val is not None else None,
        )

        duration = time.time() - start
        feature_importance = dict(
            zip(
                x_train.columns,
                model.feature_importances_.tolist(), strict=False,
            )
        ) if hasattr(model, "feature_importances_") else None

        artifact = ModelArtifact(
            model_type=ModelType.LIGHTGBM,
            task_type=task_type,
            status=ModelStatus.TRAINING,
            hyperparameters=default_params,
            feature_importance=feature_importance,
            training_duration_seconds=duration,
        )
        self._trained_models[artifact.id] = model
        return artifact

    def get_model(self, artifact_id: UUID) -> Any:
        model = self._trained_models.get(artifact_id)
        if model is None:
            raise KeyError(f"No trained model found for artifact {artifact_id}")
        return model

    def predict(
        self,
        artifact_id: UUID,
        x: pd.DataFrame,
    ) -> np.ndarray:
        model = self.get_model(artifact_id)
        return model.predict(x)

    def predict_proba(
        self,
        artifact_id: UUID,
        x: pd.DataFrame,
    ) -> np.ndarray:
        model = self.get_model(artifact_id)
        return model.predict_proba(x)
