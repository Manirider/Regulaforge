from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from regulaforge.ml.domain.enums import ModelType
from regulaforge.ml.domain.models import ModelArtifact

logger = logging.getLogger(__name__)


class ModelSerializer:
    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self._storage_path = storage_path or Path("./data/models")
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def save_model(self, model: Any, artifact: ModelArtifact) -> Path:
        model_dir = self._storage_path / str(artifact.id)
        model_dir.mkdir(parents=True, exist_ok=True)

        if artifact.model_type == ModelType.XGBOOST:
            model_path = model_dir / "model.json"
            model.save_model(str(model_path))
        elif artifact.model_type == ModelType.CATBOOST:
            model_path = model_dir / "model.cbm"
            model.save_model(str(model_path))
        elif artifact.model_type == ModelType.LIGHTGBM:
            model_path = model_dir / "model.txt"
            model.booster_.save_model(str(model_path))
        else:
            model_path = model_dir / "model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(model, f)

        metadata_path = model_dir / "metadata.json"
        metadata = {
            "artifact_id": str(artifact.id),
            "model_type": artifact.model_type.value,
            "version": artifact.version,
            "hyperparameters": artifact.hyperparameters,
            "metrics": artifact.metrics,
            "training_date": artifact.training_date.isoformat(),
            "feature_importance": artifact.feature_importance,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        logger.info("Model %s saved to %s", artifact.id, model_dir)
        return model_dir

    def load_model(self, artifact: ModelArtifact) -> Any:
        model_dir = self._storage_path / str(artifact.id)
        if not model_dir.exists():
            raise FileNotFoundError(f"Model {artifact.id} not found at {model_dir}")

        if artifact.model_type == ModelType.XGBOOST:
            import xgboost as xgb
            model_path = model_dir / "model.json"
            model = xgb.XGBClassifier()
            model.load_model(str(model_path))
        elif artifact.model_type == ModelType.CATBOOST:
            from catboost import CatBoostClassifier
            model_path = model_dir / "model.cbm"
            model = CatBoostClassifier()
            model.load_model(str(model_path))
        elif artifact.model_type == ModelType.LIGHTGBM:
            import lightgbm as lgb
            model_path = model_dir / "model.txt"
            model = lgb.Booster(model_file=str(model_path))
        else:
            model_path = model_dir / "model.pkl"
            with open(model_path, "rb") as f:
                model = pickle.load(f)

        return model

    def load_metadata(self, artifact_id: UUID) -> Optional[dict[str, Any]]:
        metadata_path = self._storage_path / str(artifact_id) / "metadata.json"
        if not metadata_path.exists():
            return None
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def list_saved_models(self) -> list[UUID]:
        return [
            UUID(p.name) for p in self._storage_path.iterdir()
            if p.is_dir() and (p / "metadata.json").exists()
        ]
