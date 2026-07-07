from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from regulaforge.ml.domain.enums import ModelStatus, ModelType, TaskType
from regulaforge.ml.domain.models import ModelArtifact

logger = logging.getLogger(__name__)


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[UUID, ModelArtifact] = {}
        self._version_counter: dict[str, int] = {}

    def register(
        self,
        artifact: ModelArtifact,
        mlflow_run_id: Optional[str] = None,
    ) -> ModelArtifact:
        key = f"{artifact.model_type.value}_{artifact.task_type.value}"
        self._version_counter[key] = self._version_counter.get(key, 0) + 1
        artifact.version = self._version_counter[key]
        artifact.mlflow_run_id = mlflow_run_id
        artifact.status = ModelStatus.STAGING
        self._models[artifact.id] = artifact
        logger.info(
            "Registered model %s v%d (%s/%s)",
            artifact.id, artifact.version,
            artifact.model_type.value, artifact.task_type.value,
        )
        return artifact

    def promote_to_production(self, model_id: UUID) -> Optional[ModelArtifact]:
        artifact = self._models.get(model_id)
        if artifact is None:
            logger.error("Model %s not found for promotion", model_id)
            return None
        current_prod = self.get_production_model(artifact.model_type, artifact.task_type)
        if current_prod and current_prod.id != model_id:
            current_prod.status = ModelStatus.DEPRECATED
            logger.info("Deprecated previous production model %s", current_prod.id)
        artifact.status = ModelStatus.PRODUCTION
        artifact.tags["promoted_at"] = datetime.utcnow().isoformat()
        logger.info("Promoted model %s to production", model_id)
        return artifact

    def archive_model(self, model_id: UUID) -> Optional[ModelArtifact]:
        artifact = self._models.get(model_id)
        if artifact is None:
            return None
        artifact.status = ModelStatus.ARCHIVED
        return artifact

    def get_model(self, model_id: UUID) -> Optional[ModelArtifact]:
        return self._models.get(model_id)

    def get_production_model(
        self,
        model_type: ModelType,
        task_type: TaskType,
    ) -> Optional[ModelArtifact]:
        for artifact in self._models.values():
            if (
                artifact.model_type == model_type
                and artifact.task_type == task_type
                and artifact.status == ModelStatus.PRODUCTION
            ):
                return artifact
        return None

    def list_models(
        self,
        model_type: Optional[ModelType] = None,
        task_type: Optional[TaskType] = None,
        status: Optional[ModelStatus] = None,
    ) -> list[ModelArtifact]:
        results = list(self._models.values())
        if model_type:
            results = [m for m in results if m.model_type == model_type]
        if task_type:
            results = [m for m in results if m.task_type == task_type]
        if status:
            results = [m for m in results if m.status == status]
        return sorted(results, key=lambda m: m.training_date, reverse=True)

    def compare_models(
        self,
        model_ids: list[UUID],
    ) -> dict[str, Any]:
        comparison: dict[str, Any] = {}
        for mid in model_ids:
            artifact = self._models.get(mid)
            if artifact:
                comparison[str(mid)] = {
                    "name": artifact.name,
                    "model_type": artifact.model_type.value,
                    "task_type": artifact.task_type.value,
                    "version": artifact.version,
                    "status": artifact.status.value,
                    "metrics": artifact.metrics,
                    "training_date": artifact.training_date.isoformat(),
                }
        return comparison
