from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd

from regulaforge.ml.domain.enums import ModelType, TaskType
from regulaforge.ml.domain.models import FeatureSet


class PipelineBase(ABC):
    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        ...

    @abstractmethod
    def build_feature_set(self) -> FeatureSet:
        ...

    @abstractmethod
    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        ...

    @abstractmethod
    def run(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_test: pd.DataFrame,
        y_test: pd.Series,
        model_type: ModelType = ModelType.XGBOOST,
        hyperparameters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        ...
