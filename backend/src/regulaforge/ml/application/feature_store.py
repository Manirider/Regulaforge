from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import numpy as np
import pandas as pd

from regulaforge.ml.domain.enums import TaskType
from regulaforge.ml.domain.models import FeatureSet

logger = logging.getLogger(__name__)


@dataclass
class FeatureTransformation:
    name: str
    transform_type: str  # "scale", "encode", "bin", "log", "date", "text"
    params: dict[str, Any] = field(default_factory=dict)


class FeatureStore:
    def __init__(self) -> None:
        self._feature_sets: dict[UUID, FeatureSet] = {}
        self._transformations: dict[str, FeatureTransformation] = {}

    def register_feature_set(self, feature_set: FeatureSet) -> UUID:
        self._feature_sets[feature_set.id] = feature_set
        logger.info("Registered feature set %s (%s)", feature_set.id, feature_set.name)
        return feature_set.id

    def get_feature_set(self, feature_set_id: UUID) -> Optional[FeatureSet]:
        return self._feature_sets.get(feature_set_id)

    def list_feature_sets(self, task_type: Optional[TaskType] = None) -> list[FeatureSet]:
        if task_type:
            return [fs for fs in self._feature_sets.values() if fs.task_type == task_type]
        return list(self._feature_sets.values())

    def register_transformation(self, transformation: FeatureTransformation) -> None:
        self._transformations[transformation.name] = transformation

    def compute_features(
        self,
        data: pd.DataFrame,
        feature_set: FeatureSet,
    ) -> pd.DataFrame:
        df = data.copy()
        for feature in feature_set.features:
            if feature.name not in df.columns:
                if feature.nullable:
                    df[feature.name] = np.nan
                else:
                    raise ValueError(f"Required feature '{feature.name}' not found in data")
        selected = [f.name for f in feature_set.features if f.name in df.columns]
        return df[selected]

    @staticmethod
    def create_risk_features(data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "amount" in df.columns and "threshold" in df.columns:
            df["amount_to_threshold_ratio"] = df["amount"] / (df["threshold"] + 1e-8)
        if "past_due_days" in df.columns:
            df["past_due_weeks"] = df["past_due_days"] / 7.0
            df["is_past_due"] = (df["past_due_days"] > 0).astype(int)
            df["log_past_due_days"] = np.log1p(df["past_due_days"])
        if "transaction_count" in df.columns:
            df["log_transaction_count"] = np.log1p(df["transaction_count"])
        if "credit_score" in df.columns:
            df["credit_score_binned"] = pd.cut(
                df["credit_score"], bins=[0, 580, 670, 740, 800, 850],
                labels=[1, 2, 3, 4, 5],
            ).astype(int)
        return df

    @staticmethod
    def create_compliance_features(data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "regulation_count" in df.columns and "days_since_last_review" in df.columns:
            df["review_frequency_score"] = df["regulation_count"] / (
                df["days_since_last_review"] + 1
            )
        if "past_violations" in df.columns:
            df["has_violations"] = (df["past_violations"] > 0).astype(int)
            df["log_violations"] = np.log1p(df["past_violations"])
        if "filing_delay_days" in df.columns:
            df["filing_delay_weeks"] = df["filing_delay_days"] / 7.0
            df["is_late_filing"] = (df["filing_delay_days"] > 0).astype(int)
        if "audit_score" in df.columns:
            df["audit_score_normalized"] = df["audit_score"] / 100.0
        return df
