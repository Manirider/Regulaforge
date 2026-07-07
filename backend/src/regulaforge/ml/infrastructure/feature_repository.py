from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import pandas as pd

from regulaforge.ml.domain.models import FeatureSet

logger = logging.getLogger(__name__)


class FeatureRepository:
    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self._storage_path = storage_path or Path("./data/features")
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[UUID, FeatureSet] = {}

    def save_feature_set(self, feature_set: FeatureSet) -> None:
        self._cache[feature_set.id] = feature_set
        path = self._storage_path / f"{feature_set.id}.json"
        data = {
            "id": str(feature_set.id),
            "name": feature_set.name,
            "features": [
                {
                    "name": f.name,
                    "feature_type": f.feature_type.value,
                    "description": f.description,
                    "feature_group": f.feature_group,
                    "source": f.source,
                    "nullable": f.nullable,
                }
                for f in feature_set.features
            ],
            "target_column": feature_set.target_column,
            "task_type": feature_set.task_type.value,
            "created_at": feature_set.created_at.isoformat(),
            "version": feature_set.version,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Saved feature set %s to %s", feature_set.id, path)

    def get_feature_set(self, feature_set_id: UUID) -> Optional[FeatureSet]:
        if feature_set_id in self._cache:
            return self._cache[feature_set_id]
        path = self._storage_path / f"{feature_set_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        from regulaforge.ml.domain.enums import FeatureType, TaskType
        from regulaforge.ml.domain.models import Feature
        features = [
            Feature(
                name=f["name"],
                feature_type=FeatureType(f["feature_type"]),
                description=f.get("description", ""),
                feature_group=f.get("feature_group", "default"),
                source=f.get("source", "raw"),
                nullable=f.get("nullable", False),
            )
            for f in data["features"]
        ]
        feature_set = FeatureSet(
            id=UUID(data["id"]),
            name=data["name"],
            features=features,
            target_column=data["target_column"],
            task_type=TaskType(data["task_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            version=data.get("version", 1),
        )
        self._cache[feature_set.id] = feature_set
        return feature_set

    def save_training_data(
        self,
        feature_set_id: UUID,
        x: pd.DataFrame,
        y: pd.Series,
    ) -> Path:
        dir_path = self._storage_path / str(feature_set_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        data_path = dir_path / "training_data.parquet"
        data = x.copy()
        data["target"] = y.values
        data.to_parquet(data_path, index=False)
        logger.info("Saved training data (%d rows) to %s", len(data), data_path)
        return data_path

    def load_training_data(
        self,
        feature_set_id: UUID,
    ) -> Optional[tuple[pd.DataFrame, pd.Series]]:
        dir_path = self._storage_path / str(feature_set_id)
        data_path = dir_path / "training_data.parquet"
        if not data_path.exists():
            return None
        data = pd.read_parquet(data_path)
        y = data["target"]
        x = data.drop(columns=["target"])
        logger.info("Loaded training data (%d rows) from %s", len(data), data_path)
        return x, y

    def list_feature_sets(self) -> list[FeatureSet]:
        for path in self._storage_path.glob("*.json"):
            fs_id = UUID(path.stem)
            if fs_id not in self._cache:
                self.get_feature_set(fs_id)
        return list(self._cache.values())
