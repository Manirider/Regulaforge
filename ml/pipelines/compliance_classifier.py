from typing import Any, Dict, List, Optional, Tuple, Union
import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
import shap
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sentence_transformers import SentenceTransformer

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None  # type: ignore

try:
    from catboost import CatBoostClassifier
except ImportError:
    CatBoostClassifier = None  # type: ignore

from .base_pipeline import BaseMLPipeline
from .config import ClassificationConfig

logger = logging.getLogger(__name__)


class ComplianceClassifierPipeline(BaseMLPipeline):
    def __init__(self, config: Optional[ClassificationConfig] = None):
        super().__init__(config or ClassificationConfig())
        self.config: ClassificationConfig = self.config  # narrow type
        self.label_encoder: Optional[LabelEncoder] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        self.scaler: Optional[StandardScaler] = None
        self.ensemble_models: List[Any] = []
        self.calibrated_model: Optional[CalibratedClassifierCV] = None

    def _get_embedding(self, texts: List[str]) -> np.ndarray:
        if self.embedding_model is None:
            logger.info("Loading embedding model: %s", self.config.embedding_model)
            self.embedding_model = SentenceTransformer(self.config.embedding_model)
        return self.embedding_model.encode(texts, show_progress_bar=False)

    def load_data(self, data_path: str, **kwargs) -> Tuple[pd.DataFrame, Union[pd.Series, np.ndarray]]:
        target_col = kwargs.get("target_col", "target")
        df = pd.read_csv(data_path)
        logger.info("Loaded %d rows with %d columns", len(df), len(df.columns))
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in data")
        y = df.pop(target_col).values
        return df, y

    def preprocess(
        self, X: pd.DataFrame, y: Optional[Union[pd.Series, np.ndarray]] = None, fit: bool = True
    ) -> Tuple[pd.DataFrame, Optional[Union[pd.Series, np.ndarray]]]:
        df = X.copy()
        if fit:
            self.label_encoder = LabelEncoder()
            text_cols = df.select_dtypes(include=["object"]).columns.tolist()
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            self._text_cols = text_cols
            self._numeric_cols = numeric_cols
        text_cols: List[str] = getattr(self, "_text_cols", [])
        numeric_cols: List[str] = getattr(self, "_numeric_cols", [])
        for col in text_cols:
            df[col] = df[col].fillna("")
        imputer = SimpleImputer(strategy="median")
        if numeric_cols:
            df[numeric_cols] = imputer.fit_transform(df[numeric_cols]) if fit else imputer.transform(df[numeric_cols])
        if y is not None and fit:
            y = self.label_encoder.fit_transform(y)
        elif y is not None:
            y = self.label_encoder.transform(y)
        return df, y

    def feature_engineer(self, X: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        df = X.copy()
        text_cols: List[str] = getattr(self, "_text_cols", [])
        numeric_cols: List[str] = getattr(self, "_numeric_cols", [])
        text_data = df[text_cols].agg(" ".join, axis=1).tolist() if text_cols else [""] * len(df)
        if fit:
            self._text_embeddings = self._get_embedding(text_data)
        else:
            self._text_embeddings = self._get_embedding(text_data)
        embedding_df = pd.DataFrame(
            self._text_embeddings,
            index=df.index,
            columns=[f"embed_{i}" for i in range(self._text_embeddings.shape[1])],
        )
        if numeric_cols:
            result = pd.concat([df[numeric_cols].reset_index(drop=True), embedding_df.reset_index(drop=True)], axis=1)
        else:
            result = embedding_df.reset_index(drop=True)
        if fit:
            self.scaler = StandardScaler()
            result = pd.DataFrame(
                self.scaler.fit_transform(result),
                columns=result.columns,
                index=result.index,
            )
            self.feature_names = result.columns.tolist()
        else:
            result = pd.DataFrame(
                self.scaler.transform(result),
                columns=result.columns,
                index=result.index,
            )
        return result

    def train(self, X_train: pd.DataFrame, y_train: Union[pd.Series, np.ndarray]) -> Any:
        self.ensemble_models = []
        if self.config.use_ensemble:
            if XGBClassifier is not None:
                xgb_model = XGBClassifier(**self.config.xgboost_params, random_state=self.config.random_state)
                xgb_model.fit(X_train, y_train)
                self.ensemble_models.append(("xgb", xgb_model))
                mlflow.log_param("xgb_trained", True)
                logger.info("XGBoost model trained")
            else:
                logger.warning("XGBoost not installed, skipping")
            if CatBoostClassifier is not None:
                cat_params = dict(self.config.catboost_params)
                cat_params["random_seed"] = self.config.random_state
                cat_model = CatBoostClassifier(**cat_params)
                cat_model.fit(X_train, y_train, verbose=False)
                self.ensemble_models.append(("catboost", cat_model))
                mlflow.log_param("catboost_trained", True)
                logger.info("CatBoost model trained")
            else:
                logger.warning("CatBoost not installed, skipping")
        lr_model = LogisticRegression(**self.config.logistic_params, random_state=self.config.random_state)
        lr_model.fit(X_train, y_train)
        self.ensemble_models.append(("lr", lr_model))
        mlflow.log_param("lr_trained", True)
        logger.info("LogisticRegression model trained")
        if len(self.ensemble_models) > 1:
            from sklearn.ensemble import VotingClassifier
            estimators = [(name, m) for name, m in self.ensemble_models]
            ensemble = VotingClassifier(estimators=estimators, voting="soft")
            ensemble.fit(X_train, y_train)
            self.model = ensemble
            logger.info("Ensemble model created with %d estimators", len(estimators))
        else:
            self.model = self.ensemble_models[0][1]
        self.calibrated_model = CalibratedClassifierCV(
            self.model, method=self.config.calibration_method, cv=3
        )
        self.calibrated_model.fit(X_train, y_train)
        logger.info("Model calibrated using %s", self.config.calibration_method)
        return self.calibrated_model

    def evaluate(self, X_test: pd.DataFrame, y_test: Union[pd.Series, np.ndarray]) -> Dict[str, float]:
        y_pred = self.calibrated_model.predict(X_test)
        y_prob = self.calibrated_model.predict_proba(X_test)
        n_classes = len(np.unique(y_test))
        metrics: Dict[str, float] = {}
        metrics["accuracy"] = float(accuracy_score(y_test, y_pred))
        metrics["precision_macro"] = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
        metrics["recall_macro"] = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
        metrics["f1_macro"] = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        if n_classes == 2:
            metrics["roc_auc"] = float(roc_auc_score(y_test, y_prob[:, 1]))
            metrics["precision"] = float(precision_score(y_test, y_pred, zero_division=0))
            metrics["recall"] = float(recall_score(y_test, y_pred, zero_division=0))
            metrics["f1"] = float(f1_score(y_test, y_pred, zero_division=0))
        else:
            try:
                metrics["roc_auc_ovr"] = float(roc_auc_score(y_test, y_prob, multi_class="ovr"))
            except ValueError:
                metrics["roc_auc_ovr"] = 0.0
        cm = confusion_matrix(y_test, y_pred)
        cm_dict = {"confusion_matrix": cm.tolist()}
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        mlflow.log_dict(cm_dict, "confusion_matrix.json")
        mlflow.log_dict(report, "classification_report.json")
        return metrics

    def explain(self, X: pd.DataFrame) -> Dict[str, Any]:
        model_for_shap = self.ensemble_models[0][1] if self.ensemble_models else self.model
        try:
            if hasattr(model_for_shap, "predict_proba"):
                explainer = shap.Explainer(model_for_shap, X, feature_names=self.feature_names)
            else:
                explainer = shap.Explainer(model_for_shap.predict, X, feature_names=self.feature_names)
            shap_values = explainer(X, max_evals=2 * X.shape[1] + 1, silent=True)
            feature_importance = np.abs(shap_values.values).mean(axis=0)
            if feature_importance.ndim > 1:
                feature_importance = feature_importance.mean(axis=1)
            top_indices = np.argsort(feature_importance)[-20:][::-1]
            top_features = {
                self.feature_names[i]: float(feature_importance[i])
                for i in top_indices
                if i < len(self.feature_names)
            }
            shap_path = Path("shap_summary.png")
            try:
                shap.summary_plot(shap_values, X, show=False)
                import matplotlib.pyplot as plt
                plt.savefig(str(shap_path), bbox_inches="tight")
                plt.close()
                mlflow.log_artifact(str(shap_path))
            except Exception:
                logger.warning("SHAP plot generation failed", exc_info=True)
            return {
                "feature_importance": top_features,
                "shap_values_shape": list(shap_values.values.shape),
                "explanation_method": "shap",
            }
        except Exception as exc:
            logger.warning("SHAP explanation failed: %s", exc)
            return {"feature_importance": {}, "explanation_method": "shap", "error": str(exc)}

    def save_model(self, path: Optional[str] = None) -> str:
        if path is None:
            path = str(Path("models") / f"compliance_classifier_{self.version}")
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)
        model_info = mlflow.sklearn.log_model(
            sk_model=self.calibrated_model,
            artifact_path="classification_model",
            registered_model_name="ComplianceClassifier",
            serialization_format="cloudpickle",
        )
        params_path = save_path / "pipeline_config.json"
        config_dict = {
            "version": self.version,
            "feature_names": self.feature_names,
            "classes": self.label_encoder.classes_.tolist() if self.label_encoder else [],
            "config": {
                k: v for k, v in self.config.__dict__.items() if not isinstance(v, (list, tuple, dict)) or k in ("quantile_alphas", "autoencoder_layers")
            },
        }
        with open(params_path, "w") as f:
            json.dump(config_dict, f, indent=2, default=str)
        mlflow.log_artifact(str(params_path))
        logger.info("Model saved to %s", model_info.model_uri)
        return model_info.model_uri

    def deploy(self, model_uri: str, stage: str = "Staging") -> Dict[str, Any]:
        client = mlflow.tracking.MlflowClient()
        model_name = "ComplianceClassifier"
        try:
            result = client.create_registered_model(model_name)
        except mlflow.exceptions.MlflowException:
            result = client.get_registered_model(model_name)
        version = client.create_model_version(
            name=model_name,
            source=model_uri,
            run_id=mlflow.active_run().info.run_id if mlflow.active_run() else None,
        )
        client.transition_model_version_stage(
            name=model_name, version=version.version, stage=stage
        )
        logger.info("Model %s version %s promoted to %s", model_name, version.version, stage)
        return {
            "model_name": model_name,
            "version": version.version,
            "stage": stage,
            "model_uri": model_uri,
        }
