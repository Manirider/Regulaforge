from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from regulaforge.ml.domain.enums import ModelType, TaskType
from regulaforge.ml.domain.models import CVResult

logger = logging.getLogger(__name__)


class CrossValidator:
    def __init__(self, n_folds: int = 5, shuffle: bool = True, random_state: int = 42) -> None:
        self.n_folds = n_folds
        self.shuffle = shuffle
        self.random_state = random_state

    def cross_validate(
        self,
        model_type: ModelType,
        x: pd.DataFrame,
        y: pd.Series,
        params: Optional[dict[str, Any]] = None,
        task_type: TaskType = TaskType.RISK_CLASSIFICATION,
        metrics: Optional[list[str]] = None,
    ) -> list[CVResult]:
        params = params or {}
        metrics = metrics or ["accuracy", "precision", "recall", "f1", "roc_auc"]
        from collections import Counter

        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        min_class_count = min(Counter(y).values())
        n_splits = min(self.n_folds, len(x) - 1, min_class_count)
        if n_splits < 2:
            logger.warning(
                "Insufficient data for cross-validation: n_samples=%d, min_class_count=%d, n_splits=%d. Skipping CV.",
                len(x), min_class_count, n_splits,
            )
            return []
        kfold = StratifiedKFold(
            n_splits=n_splits,
            shuffle=self.shuffle,
            random_state=self.random_state,
        )

        results: list[CVResult] = []
        for fold, (train_idx, val_idx) in enumerate(kfold.split(x, y)):
            x_train, x_val = x.iloc[train_idx], x.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model = self._build_model(model_type, params)
            model.fit(x_train, y_train)

            train_preds = model.predict(x_train)
            val_preds = model.predict(x_val)

            fold_metrics: dict[str, float] = {}
            if "accuracy" in metrics:
                fold_metrics["accuracy"] = float(accuracy_score(y_val, val_preds))
            if "precision" in metrics:
                fold_metrics["precision"] = float(
                    precision_score(y_val, val_preds, average="weighted", zero_division=0)
                )
            if "recall" in metrics:
                fold_metrics["recall"] = float(
                    recall_score(y_val, val_preds, average="weighted", zero_division=0)
                )
            if "f1" in metrics:
                fold_metrics["f1"] = float(
                    f1_score(y_val, val_preds, average="weighted", zero_division=0)
                )
            if "roc_auc" in metrics and len(np.unique(y)) == 2:
                try:
                    val_proba = model.predict_proba(x_val)[:, 1]
                    fold_metrics["roc_auc"] = float(roc_auc_score(y_val, val_proba))
                except Exception:
                    pass

            train_acc = float(accuracy_score(y_train, train_preds))
            val_acc = float(accuracy_score(y_val, val_preds))

            cv_result = CVResult(
                fold=fold,
                metrics=fold_metrics,
                train_score=train_acc,
                val_score=val_acc,
                n_train_samples=len(x_train),
                n_val_samples=len(x_val),
            )
            results.append(cv_result)
            logger.debug("Fold %d: train=%.4f val=%.4f", fold, train_acc, val_acc)

        mean_val = np.mean([r.val_score for r in results])
        std_val = np.std([r.val_score for r in results])
        logger.info(
            "CV complete: %d folds, mean=%.4f, std=%.4f",
            len(results), mean_val, std_val,
        )
        return results

    def _build_model(self, model_type: ModelType, params: dict[str, Any]) -> Any:
        if model_type == ModelType.XGBOOST:
            import xgboost as xgb
            return xgb.XGBClassifier(**params, verbosity=0, enable_categorical=True)
        elif model_type == ModelType.CATBOOST:
            from catboost import CatBoostClassifier
            return CatBoostClassifier(**params, verbose=False)
        elif model_type == ModelType.LIGHTGBM:
            import lightgbm as lgb
            return lgb.LGBMClassifier(**params, verbose=-1)
        raise ValueError(f"Unsupported model type: {model_type}")

    def summary(self, results: list[CVResult]) -> dict[str, Any]:
        if not results:
            return {}
        val_scores = [r.val_score for r in results]
        return {
            "n_folds": len(results),
            "mean_val_score": float(np.mean(val_scores)),
            "std_val_score": float(np.std(val_scores)),
            "min_val_score": float(np.min(val_scores)),
            "max_val_score": float(np.max(val_scores)),
            "mean_train_score": float(np.mean([r.train_score for r in results])),
            "fold_scores": {
                f"fold_{r.fold}": {
                    "val": r.val_score,
                    "train": r.train_score,
                    "n_train": r.n_train_samples,
                    "n_val": r.n_val_samples,
                }
                for r in results
            },
        }
