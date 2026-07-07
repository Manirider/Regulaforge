from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

from regulaforge.ml.domain.enums import ModelType, TaskType
from regulaforge.ml.domain.models import EvaluationResult

logger = logging.getLogger(__name__)


class Evaluator:
    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []

    def evaluate(
        self,
        model: Any,
        x_test: pd.DataFrame,
        y_test: pd.Series,
        _model_type: Optional[ModelType] = None,
        _task_type: TaskType = TaskType.RISK_CLASSIFICATION,
    ) -> EvaluationResult:
        from sklearn.metrics import (
            accuracy_score,
            classification_report,
            confusion_matrix,
            f1_score,
            log_loss,
            precision_score,
            recall_score,
            roc_auc_score,
        )

        y_pred = model.predict(x_test)
        result = EvaluationResult(
            accuracy=float(accuracy_score(y_test, y_pred)),
            precision=float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
            recall=float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
            f1_score=float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
            confusion_matrix=confusion_matrix(y_test, y_pred).tolist(),
            classification_report=classification_report(y_test, y_pred, output_dict=True, zero_division=0),
        )

        try:
            y_proba = model.predict_proba(x_test)
            n_classes = y_proba.shape[1]
            if n_classes == 2:
                result.auc_roc = float(roc_auc_score(y_test, y_proba[:, 1]))
                result.log_loss = float(log_loss(y_test, y_proba))
            else:
                result.auc_roc = float(roc_auc_score(y_test, y_proba, multi_class="ovo"))
                result.log_loss = float(log_loss(y_test, y_proba))
        except Exception as exc:
            logger.debug("Could not compute proba-based metrics: %s", exc)

        self._history.append({
            "accuracy": result.accuracy,
            "precision": result.precision,
            "recall": result.recall,
            "f1_score": result.f1_score,
            "auc_roc": result.auc_roc,
        })
        return result

    def compare_models(
        self,
        results: dict[str, EvaluationResult],
    ) -> dict[str, Any]:
        comparison: dict[str, Any] = {}
        for name, result in results.items():
            comparison[name] = {
                "accuracy": result.accuracy,
                "precision": result.precision,
                "recall": result.recall,
                "f1": result.f1_score,
                "auc_roc": result.auc_roc,
            }
        return comparison

    def get_history(self) -> list[dict[str, Any]]:
        return self._history

    @staticmethod
    def calculate_optimal_threshold(
        model: Any,
        x_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> dict[str, Any]:
        from sklearn.metrics import f1_score

        y_proba = model.predict_proba(x_val)[:, 1]
        thresholds = np.linspace(0.1, 0.9, 81)
        best_threshold = 0.5
        best_f1 = 0.0
        results: list[dict[str, float]] = []

        for threshold in thresholds:
            y_pred = (y_proba >= threshold).astype(int)
            score = f1_score(y_val, y_pred, zero_division=0)
            results.append({"threshold": float(threshold), "f1": float(score)})
            if score > best_f1:
                best_f1 = score
                best_threshold = threshold

        return {
            "best_threshold": float(best_threshold),
            "best_f1": float(best_f1),
            "threshold_curve": results,
        }
