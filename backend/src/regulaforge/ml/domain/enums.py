from __future__ import annotations

from enum import Enum


class ModelType(str, Enum):
    XGBOOST = "xgboost"
    CATBOOST = "catboost"
    LIGHTGBM = "lightgbm"


class TaskType(str, Enum):
    RISK_CLASSIFICATION = "risk_classification"
    COMPLIANCE_PREDICTION = "compliance_prediction"


class FeatureType(str, Enum):
    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    TEXT = "text"
    BOOLEAN = "boolean"
    DATETIME = "datetime"


class ModelStatus(str, Enum):
    TRAINING = "training"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class MetricType(str, Enum):
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1 = "f1"
    F1_MICRO = "f1_micro"
    F1_MACRO = "f1_macro"
    F1_WEIGHTED = "f1_weighted"
    AUC_ROC = "auc_roc"
    AUC_PR = "auc_pr"
    LOG_LOSS = "log_loss"
    BCE = "binary_crossentropy"
    MCC = "matthews_correlation"
    COHEN_KAPPA = "cohen_kappa"
    SPECIFICITY = "specificity"
    NEGATIVE_PREDICTIVE_VALUE = "npv"
    FALSE_POSITIVE_RATE = "fpr"
    FALSE_NEGATIVE_RATE = "fnr"


class DriftStatus(str, Enum):
    NO_DRIFT = "no_drift"
    WARNING = "warning"
    DRIFT_DETECTED = "drift_detected"
