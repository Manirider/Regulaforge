from dataclasses import dataclass, field
from typing import List, Optional, Literal


@dataclass
class PipelineConfig:
    experiment_name: str = "regulaforge_default"
    tracking_uri: Optional[str] = None
    model_registry_uri: Optional[str] = None
    random_state: int = 42
    test_size: float = 0.2
    cv_folds: int = 5
    n_jobs: int = -1
    verbose: bool = True


@dataclass
class ClassificationConfig(PipelineConfig):
    experiment_name: str = "regulaforge_classification"
    class_weight: Literal["balanced", None] = "balanced"
    threshold: float = 0.5
    calibration_method: Literal["sigmoid", "isotonic"] = "sigmoid"
    multi_label: bool = False
    use_ensemble: bool = True
    xgboost_params: dict = field(default_factory=lambda: {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "eval_metric": "logloss",
    })
    catboost_params: dict = field(default_factory=lambda: {
        "iterations": 300,
        "depth": 6,
        "learning_rate": 0.05,
        "l2_leaf_reg": 3.0,
        "border_count": 128,
        "verbose": False,
    })
    logistic_params: dict = field(default_factory=lambda: {
        "C": 1.0,
        "penalty": "l2",
        "solver": "lbfgs",
        "max_iter": 1000,
    })
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class RiskScoringConfig(PipelineConfig):
    experiment_name: str = "regulaforge_risk_scoring"
    quantile_alphas: List[float] = field(default_factory=lambda: [0.05, 0.5, 0.95])
    uncertainty_method: Literal["quantile", "dropout", "ensemble"] = "quantile"
    n_estimators: int = 500
    max_depth: int = 5
    learning_rate: float = 0.03
    subsample: float = 0.8
    early_stopping_rounds: int = 50
    min_child_weight: int = 3
    reg_lambda: float = 1.0
    reg_alpha: float = 0.1


@dataclass
class AnomalyConfig(PipelineConfig):
    experiment_name: str = "regulaforge_anomaly_detection"
    contamination: float = 0.1
    n_estimators_if: int = 200
    max_samples_if: float = 0.8
    max_features_if: float = 0.8
    autoencoder_layers: List[int] = field(default_factory=lambda: [64, 32, 16, 32, 64])
    autoencoder_epochs: int = 100
    autoencoder_batch_size: int = 32
    autoencoder_learning_rate: float = 0.001
    ensemble_weight_if: float = 0.4
    ensemble_weight_ae: float = 0.6
    drift_detection_window: int = 100
    drift_significance_level: float = 0.05
