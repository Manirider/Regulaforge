from __future__ import annotations

from uuid import uuid4

import pytest
from regulaforge.ml.application.model_registry import ModelRegistry
from regulaforge.ml.domain.enums import ModelStatus, ModelType, TaskType
from regulaforge.ml.domain.models import ModelArtifact


class TestModelRegistry:
    @pytest.fixture
    def registry(self):
        return ModelRegistry()

    @pytest.fixture
    def artifact(self):
        return ModelArtifact(
            name="test_model",
            model_type=ModelType.XGBOOST,
            task_type=TaskType.RISK_CLASSIFICATION,
        )

    def test_register_increments_version(self, registry, artifact):
        a1 = registry.register(artifact)
        assert a1.version == 1
        a2 = registry.register(ModelArtifact(model_type=ModelType.XGBOOST, task_type=TaskType.RISK_CLASSIFICATION))
        assert a2.version == 2

    def test_register_sets_staging(self, registry, artifact):
        registered = registry.register(artifact)
        assert registered.status == ModelStatus.STAGING

    def test_get_model(self, registry, artifact):
        registered = registry.register(artifact)
        assert registry.get_model(registered.id) is registered

    def test_get_model_not_found(self, registry):
        assert registry.get_model(uuid4()) is None

    def test_promote_to_production(self, registry, artifact):
        registered = registry.register(artifact)
        promoted = registry.promote_to_production(registered.id)
        assert promoted is not None
        assert promoted.status == ModelStatus.PRODUCTION

    def test_promote_deprecates_previous(self, registry):
        a1 = registry.register(ModelArtifact(model_type=ModelType.XGBOOST, task_type=TaskType.RISK_CLASSIFICATION))
        a2 = registry.register(ModelArtifact(model_type=ModelType.XGBOOST, task_type=TaskType.RISK_CLASSIFICATION))
        registry.promote_to_production(a1.id)
        registry.promote_to_production(a2.id)
        assert registry.get_model(a1.id).status == ModelStatus.DEPRECATED
        assert registry.get_model(a2.id).status == ModelStatus.PRODUCTION

    def test_promote_not_found(self, registry):
        assert registry.promote_to_production(uuid4()) is None

    def test_archive_model(self, registry, artifact):
        registered = registry.register(artifact)
        archived = registry.archive_model(registered.id)
        assert archived is not None
        assert archived.status == ModelStatus.ARCHIVED

    def test_archive_not_found(self, registry):
        assert registry.archive_model(uuid4()) is None

    def test_get_production_model(self, registry, artifact):
        registered = registry.register(artifact)
        registry.promote_to_production(registered.id)
        prod = registry.get_production_model(ModelType.XGBOOST, TaskType.RISK_CLASSIFICATION)
        assert prod is not None
        assert prod.id == registered.id

    def test_get_production_model_not_found(self, registry):
        prod = registry.get_production_model(ModelType.XGBOOST, TaskType.RISK_CLASSIFICATION)
        assert prod is None

    def test_list_models_filters(self, registry):
        a1 = registry.register(ModelArtifact(model_type=ModelType.XGBOOST, task_type=TaskType.RISK_CLASSIFICATION))
        a2 = registry.register(ModelArtifact(model_type=ModelType.CATBOOST, task_type=TaskType.COMPLIANCE_PREDICTION))
        assert len(registry.list_models(model_type=ModelType.XGBOOST)) == 1
        assert len(registry.list_models(task_type=TaskType.COMPLIANCE_PREDICTION)) == 1
        assert len(registry.list_models()) == 2

    def test_list_models_sorted_by_date(self, registry):
        a1 = registry.register(ModelArtifact(model_type=ModelType.XGBOOST, task_type=TaskType.RISK_CLASSIFICATION))
        import time
        time.sleep(0.01)
        a2 = registry.register(ModelArtifact(model_type=ModelType.XGBOOST, task_type=TaskType.RISK_CLASSIFICATION))
        models = registry.list_models()
        assert models[0].id == a2.id

    def test_compare_models(self, registry, artifact):
        a1 = registry.register(artifact)
        a2 = registry.register(ModelArtifact(model_type=ModelType.CATBOOST, task_type=TaskType.RISK_CLASSIFICATION))
        comparison = registry.compare_models([a1.id, a2.id])
        assert len(comparison) == 2
        assert str(a1.id) in comparison
