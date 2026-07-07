from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from regulaforge.ml.application.cross_validator import CrossValidator
from regulaforge.ml.application.evaluator import Evaluator
from regulaforge.ml.application.feature_store import FeatureStore
from regulaforge.ml.application.model_registry import ModelRegistry
from regulaforge.ml.application.model_trainer import ModelTrainer, _convert_categorical
from regulaforge.ml.domain.enums import FeatureType, ModelType, TaskType
from regulaforge.ml.domain.models import Feature, FeatureSet
from regulaforge.ml.pipelines.base import PipelineBase

logger = logging.getLogger(__name__)


class CompliancePredictionPipeline(PipelineBase):
    def __init__(
        self,
        feature_store: Optional[FeatureStore] = None,
        trainer: Optional[ModelTrainer] = None,
        evaluator: Optional[Evaluator] = None,
        registry: Optional[ModelRegistry] = None,
        validator: Optional[CrossValidator] = None,
    ) -> None:
        self.feature_store = feature_store or FeatureStore()
        self.trainer = trainer or ModelTrainer()
        self.evaluator = evaluator or Evaluator()
        self.registry = registry or ModelRegistry()
        self.validator = validator or CrossValidator(n_folds=5)

    @property
    def task_type(self) -> TaskType:
        return TaskType.COMPLIANCE_PREDICTION

    def build_feature_set(self) -> FeatureSet:
        features = [
            Feature(name="regulation_count", feature_type=FeatureType.NUMERICAL, description="Number of regulations"),
            Feature(name="days_since_last_review", feature_type=FeatureType.NUMERICAL, description="Days since last review"),  # noqa: E501
            Feature(name="past_violations", feature_type=FeatureType.NUMERICAL, description="Past violation count"),
            Feature(name="filing_delay_days", feature_type=FeatureType.NUMERICAL, description="Filing delay in days"),
            Feature(name="audit_score", feature_type=FeatureType.NUMERICAL, description="Audit score"),
            Feature(name="entity_size", feature_type=FeatureType.CATEGORICAL, description="Entity size category"),
            Feature(name="sector", feature_type=FeatureType.CATEGORICAL, description="Business sector"),
            Feature(name="jurisdiction", feature_type=FeatureType.CATEGORICAL, description="Regulatory jurisdiction"),
            Feature(name="review_frequency_score", feature_type=FeatureType.NUMERICAL, description="Review frequency"),
            Feature(name="has_violations", feature_type=FeatureType.BOOLEAN, description="Has past violations"),
            Feature(name="log_violations", feature_type=FeatureType.NUMERICAL, description="Log violation count"),
            Feature(name="filing_delay_weeks", feature_type=FeatureType.NUMERICAL, description="Filing delay in weeks"),
            Feature(name="is_late_filing", feature_type=FeatureType.BOOLEAN, description="Is late filing"),
            Feature(name="audit_score_normalized", feature_type=FeatureType.NUMERICAL, description="Normalized audit score"),  # noqa: E501
        ]
        return FeatureSet(
            name="compliance_prediction_v1",
            features=features,
            target_column="is_compliant",
            task_type=self.task_type,
        )

    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        return FeatureStore.create_compliance_features(data)

    def run(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_test: pd.DataFrame,
        y_test: pd.Series,
        model_type: ModelType = ModelType.XGBOOST,
        hyperparameters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        x_train_fe = _convert_categorical(self.prepare_features(x_train))
        x_test_fe = _convert_categorical(self.prepare_features(x_test))

        artifact = self.trainer.train(
            model_type=model_type,
            x_train=x_train_fe,
            y_train=y_train,
            hyperparameters=hyperparameters,
            task_type=self.task_type,
        )
        registered = self.registry.register(artifact)
        model = self.trainer.get_model(artifact.id)
        eval_result = self.evaluator.evaluate(model, x_test_fe, y_test)
        cv_results = self.validator.cross_validate(
            model_type=model_type,
            x=x_train_fe,
            y=y_train,
            params=hyperparameters,
            task_type=self.task_type,
        )
        cv_summary = self.validator.summary(cv_results)

        return {
            "artifact": registered,
            "evaluation": eval_result,
            "cv_summary": cv_summary,
        }
