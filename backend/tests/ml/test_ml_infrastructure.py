from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest
from regulaforge.ml.application.model_trainer import ModelTrainer
from regulaforge.ml.domain.enums import FeatureType, ModelType, TaskType
from regulaforge.ml.domain.models import Feature, FeatureSet, ModelArtifact
from regulaforge.ml.infrastructure.feature_repository import FeatureRepository
from regulaforge.ml.infrastructure.model_serializer import ModelSerializer


class TestFeatureRepository:
    @pytest.fixture
    def repo(self, tmp_path: Path) -> FeatureRepository:
        return FeatureRepository(storage_path=tmp_path / "features")

    def test_save_and_get_feature_set(self, repo: FeatureRepository) -> None:
        fs = FeatureSet(
            name="test",
            features=[Feature(name="a", feature_type=FeatureType.NUMERICAL)],
        )
        repo.save_feature_set(fs)
        loaded = repo.get_feature_set(fs.id)
        assert loaded is not None
        assert loaded.name == "test"
        assert len(loaded.features) == 1

    def test_get_feature_set_not_found(self, repo: FeatureRepository) -> None:
        assert repo.get_feature_set(uuid4()) is None

    def test_save_and_load_training_data(self, repo: FeatureRepository) -> None:
        fs_id = uuid4()
        X = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        y = pd.Series([0, 1, 0])
        repo.save_training_data(fs_id, X, y)
        loaded = repo.load_training_data(fs_id)
        assert loaded is not None
        X_loaded, y_loaded = loaded
        assert list(X_loaded.columns) == ["a", "b"]
        assert list(y_loaded) == [0, 1, 0]

    def test_list_feature_sets(self, repo: FeatureRepository) -> None:
        repo.save_feature_set(FeatureSet(name="fs1"))
        repo.save_feature_set(FeatureSet(name="fs2"))
        assert len(repo.list_feature_sets()) == 2


class TestModelSerializer:
    @pytest.fixture
    def serializer(self, tmp_path: Path) -> ModelSerializer:
        return ModelSerializer(storage_path=tmp_path / "models")

    def test_save_and_load_xgboost(self, serializer: ModelSerializer) -> None:
        trainer = ModelTrainer()
        X = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 3, 4, 5]})
        y = pd.Series([0, 0, 1, 1])
        artifact = trainer.train(ModelType.XGBOOST, X, y)
        model = trainer.get_model(artifact.id)
        path = serializer.save_model(model, artifact)
        assert path.exists()
        loaded = serializer.load_model(artifact)
        preds = loaded.predict(X)
        assert len(preds) == 4

    def test_load_metadata(self, serializer: ModelSerializer) -> None:
        trainer = ModelTrainer()
        X = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 3, 4, 5]})
        y = pd.Series([0, 0, 1, 1])
        artifact = trainer.train(ModelType.XGBOOST, X, y)
        model = trainer.get_model(artifact.id)
        serializer.save_model(model, artifact)
        metadata = serializer.load_metadata(artifact.id)
        assert metadata is not None
        assert metadata["model_type"] == "xgboost"

    def test_load_metadata_not_found(self, serializer: ModelSerializer) -> None:
        assert serializer.load_metadata(uuid4()) is None

    def test_list_saved_models(self, serializer: ModelSerializer) -> None:
        trainer = ModelTrainer()
        X = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 3, 4, 5]})
        y = pd.Series([0, 0, 1, 1])
        artifact = trainer.train(ModelType.XGBOOST, X, y)
        model = trainer.get_model(artifact.id)
        serializer.save_model(model, artifact)
        saved = serializer.list_saved_models()
        assert artifact.id in saved
