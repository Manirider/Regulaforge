from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import pandas as pd

from regulaforge.ml.domain.enums import ModelType, TaskType
from regulaforge.ml.domain.models import RetrainingJob

logger = logging.getLogger(__name__)


class Retrainer:
    def __init__(self) -> None:
        self._jobs: dict[UUID, RetrainingJob] = {}

    def create_retraining_job(
        self,
        model_id: UUID,
        trigger_reason: str = "scheduled",
    ) -> RetrainingJob:
        job = RetrainingJob(
            model_id=model_id,
            trigger_reason=trigger_reason,
            status="pending",
        )
        self._jobs[job.id] = job
        logger.info("Retraining job %s created for model %s", job.id, model_id)
        return job

    def execute_retraining(
        self,
        job_id: UUID,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        model_type: ModelType,
        task_type: TaskType,
        hyperparameters: Optional[dict[str, Any]] = None,
        current_model_metrics: Optional[dict[str, float]] = None,
    ) -> RetrainingJob:

        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"Retraining job {job_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.metrics_before = current_model_metrics

        try:
            from regulaforge.ml.application.model_trainer import ModelTrainer

            trainer = ModelTrainer()
            new_artifact = trainer.train(
                model_type=model_type,
                x_train=x_train,
                y_train=y_train,
                hyperparameters=hyperparameters,
                task_type=task_type,
            )

            from regulaforge.ml.application.evaluator import Evaluator
            evaluator = Evaluator()
            eval_result = evaluator.evaluate(trainer.get_model(new_artifact.id), x_train, y_train)

            job.metrics_after = {
                "accuracy": eval_result.accuracy,
                "precision": eval_result.precision,
                "recall": eval_result.recall,
                "f1": eval_result.f1_score,
                "auc_roc": eval_result.auc_roc,
            }
            job.new_model_id = new_artifact.id
            job.status = "completed"
            job.completed_at = datetime.utcnow()

            improvement = ""
            if current_model_metrics and "f1" in current_model_metrics and job.metrics_after:
                delta = job.metrics_after.get("f1", 0) - current_model_metrics.get("f1", 0)
                improvement = f" F1 delta: {delta:+.4f}"
            logger.info("Retraining job %s completed.%s", job_id, improvement)

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            logger.error("Retraining job %s failed: %s", job_id, exc)

        return job

    def get_job(self, job_id: UUID) -> Optional[RetrainingJob]:
        return self._jobs.get(job_id)

    def list_jobs(self, status: Optional[str] = None) -> list[RetrainingJob]:
        if status:
            return [j for j in self._jobs.values() if j.status == status]
        return list(self._jobs.values())
