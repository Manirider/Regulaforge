from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.ml.domain.enums import (
    DriftStatus,
    FeatureType,
    MetricType,
    ModelStatus,
    ModelType,
    TaskType,
)


@dataclass
class Feature:
    name: str
    feature_type: FeatureType
    description: str = ""
    feature_group: str = "default"
    source: str = "raw"
    nullable: bool = False
    encoding: Optional[dict[str, Any]] = None


@dataclass
class FeatureSet:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    features: list[Feature] = field(default_factory=list)
    target_column: str = "target"
    task_type: TaskType = TaskType.RISK_CLASSIFICATION
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1


@dataclass
class HyperparameterSpace:
    name: str
    param_name: str
    param_type: str  # "int", "float", "categorical"
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[list[Any]] = None
    log: bool = False


@dataclass
class HyperparameterSuggestion:
    params: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    trial_number: int = 0


@dataclass
class ExperimentMetric:
    metric_type: MetricType
    value: float
    std: Optional[float] = None


@dataclass
class Experiment:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    model_type: ModelType = ModelType.XGBOOST
    task_type: TaskType = TaskType.RISK_CLASSIFICATION
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    metrics: list[ExperimentMetric] = field(default_factory=list)
    best_score: float = 0.0
    best_params: dict[str, Any] = field(default_factory=dict)
    n_trials: int = 0
    status: str = "pending"
    mlflow_run_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class CVResult:
    fold: int
    metrics: dict[str, float] = field(default_factory=dict)
    train_score: float = 0.0
    val_score: float = 0.0
    n_train_samples: int = 0
    n_val_samples: int = 0


@dataclass
class EvaluationResult:
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.0
    log_loss: float = 0.0
    confusion_matrix: Optional[list[list[int]]] = None
    classification_report: Optional[dict[str, Any]] = None
    per_class_metrics: Optional[dict[str, dict[str, float]]] = None
    threshold_metrics: Optional[dict[str, list[float]]] = None
    additional_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class ModelArtifact:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    model_type: ModelType = ModelType.XGBOOST
    task_type: TaskType = TaskType.RISK_CLASSIFICATION
    version: int = 1
    status: ModelStatus = ModelStatus.STAGING
    mlflow_run_id: Optional[str] = None
    mlflow_model_uri: Optional[str] = None
    feature_set_id: Optional[UUID] = None
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    feature_importance: Optional[dict[str, float]] = None
    training_duration_seconds: float = 0.0
    training_date: datetime = field(default_factory=datetime.utcnow)
    dataset_hash: Optional[str] = None
    experiment_id: Optional[UUID] = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class SHAPExplanation:
    feature_names: list[str] = field(default_factory=list)
    shap_values: Optional[list[list[float]]] = None
    base_value: float = 0.0
    expected_value: float = 0.0
    feature_importance: dict[str, float] = field(default_factory=dict)
    top_features: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class LIMEExplanation:
    feature_names: list[str] = field(default_factory=list)
    feature_weights: dict[str, float] = field(default_factory=dict)
    prediction: float = 0.0
    confidence: float = 0.0
    top_features: list[tuple[str, float]] = field(default_factory=list)
    intercept: float = 0.0


@dataclass
class DriftReport:
    feature_name: str
    drift_score: float
    p_value: float
    status: DriftStatus
    reference_stats: Optional[dict[str, float]] = None
    current_stats: Optional[dict[str, float]] = None


@dataclass
class MonitorReport:
    id: UUID = field(default_factory=uuid4)
    model_id: UUID = field(default_factory=uuid4)
    model_version: int = 1
    overall_status: DriftStatus = DriftStatus.NO_DRIFT
    feature_drift_reports: list[DriftReport] = field(default_factory=list)
    data_drift_score: float = 0.0
    concept_drift_score: float = 0.0
    prediction_drift_score: float = 0.0
    accuracy_drift: float = 0.0
    sample_size: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    alert_triggered: bool = False


@dataclass
class RetrainingJob:
    id: UUID = field(default_factory=uuid4)
    model_id: UUID = field(default_factory=uuid4)
    trigger_reason: str = "scheduled"
    status: str = "pending"
    new_model_id: Optional[UUID] = None
    metrics_before: Optional[dict[str, float]] = None
    metrics_after: Optional[dict[str, float]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
