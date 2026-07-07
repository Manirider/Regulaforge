from typing import Any, Dict, List, Optional, Tuple, Union
import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
import mlflow.pytorch
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.covariance import EllipticEnvelope
from scipy.stats import ks_2samp, wasserstein_distance

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from .base_pipeline import BaseMLPipeline
from .config import AnomalyConfig

logger = logging.getLogger(__name__)


class Autoencoder(nn.Module):
    def __init__(self, input_dim: int, layers: List[int]):
        super().__init__()
        encoder_layers = []
        decoder_layers = []
        prev = input_dim
        half = len(layers) // 2
        for i, size in enumerate(layers):
            encoder_layers.append(nn.Linear(prev, size))
            if i < half:
                encoder_layers.append(nn.ReLU())
            else:
                encoder_layers.append(nn.ReLU())
            prev = size
        self.encoder = nn.Sequential(*encoder_layers)
        bottleneck = layers[half] if half < len(layers) else layers[-1]
        decoder_layers_rev = []
        prev = bottleneck
        for i, size in enumerate(reversed(layers)):
            decoder_layers_rev.append(nn.Linear(prev, size))
            decoder_layers_rev.append(nn.ReLU())
            prev = size
        decoder_layers_rev.append(nn.Linear(prev, input_dim))
        self.decoder = nn.Sequential(*decoder_layers_rev)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


class ComplianceAnomalyDetector(BaseMLPipeline):
    def __init__(self, config: Optional[AnomalyConfig] = None):
        super().__init__(config or AnomalyConfig())
        self.config: AnomalyConfig = self.config
        self.scaler: Optional[StandardScaler] = None
        self.label_encoders: Dict[str, LabelEncoder] = {}
        self.isolation_forest: Optional[IsolationForest] = None
        self.autoencoder_model: Optional[Autoencoder] = None
        self.reference_data: Optional[pd.DataFrame] = None
        self.categorical_cols: List[str] = []
        self.numeric_cols: List[str] = []
        self.input_dim: int = 0

    def load_data(self, data_path: str, **kwargs) -> Tuple[pd.DataFrame, Union[pd.Series, np.ndarray]]:
        df = pd.read_csv(data_path)
        logger.info("Loaded %d rows with %d columns", len(df), len(df.columns))
        y = np.zeros(len(df), dtype=int)
        if "anomaly_label" in df.columns:
            y = df.pop("anomaly_label").values.astype(int)
        return df, y

    def preprocess(
        self, X: pd.DataFrame, y: Optional[Union[pd.Series, np.ndarray]] = None, fit: bool = True
    ) -> Tuple[pd.DataFrame, Optional[Union[pd.Series, np.ndarray]]]:
        df = X.copy()
        self.categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        self.numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if fit:
            self.label_encoders = {}
        for col in self.categorical_cols:
            df[col] = df[col].fillna("MISSING").astype(str)
            if fit:
                self.label_encoders[col] = LabelEncoder()
                df[col] = self.label_encoders[col].fit_transform(df[col])
            else:
                le = self.label_encoders.get(col)
                if le:
                    known = set(le.classes_)
                    df[col] = df[col].map(lambda v: v if v in known else "MISSING")
                    df[col] = df[col].astype(str)
                    df[col] = le.transform(df[col])
        num_imputer = SimpleImputer(strategy="median")
        if self.numeric_cols:
            df[self.numeric_cols] = (
                num_imputer.fit_transform(df[self.numeric_cols])
                if fit
                else num_imputer.transform(df[self.numeric_cols])
            )
        if fit:
            self.scaler = StandardScaler()
            df = pd.DataFrame(
                self.scaler.fit_transform(df), columns=df.columns, index=df.index
            )
        else:
            df = pd.DataFrame(
                self.scaler.transform(df), columns=df.columns, index=df.index
            )
        return df, y

    def feature_engineer(self, X: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        df = X.copy()
        temporal_cols = [c for c in df.columns if any(t in c.lower() for t in ["time", "date", "month", "quarter", "year", "week"])]
        for col in temporal_cols:
            if col in df.columns:
                df[f"{col}_sin"] = np.sin(2 * np.pi * df[col] / df[col].max()) if df[col].max() > 0 else 0
                df[f"{col}_cos"] = np.cos(2 * np.pi * df[col] / df[col].max()) if df[col].max() > 0 else 0
        coverage_cols = [c for c in df.columns if "cover" in c.lower() or "regulat" in c.lower()]
        if len(coverage_cols) >= 2:
            df["coverage_diversity"] = df[coverage_cols].std(axis=1)
            df["coverage_mean"] = df[coverage_cols].mean(axis=1)
        finding_cols = [c for c in df.columns if "finding" in c.lower() or "violation" in c.lower()]
        if finding_cols:
            df["finding_count"] = df[finding_cols].sum(axis=1) if all(t in df.columns for t in finding_cols) else 0
        if fit:
            self.feature_names = df.columns.tolist()
            self.input_dim = df.shape[1]
        return df

    def _train_autoencoder(self, X_train: pd.DataFrame) -> Autoencoder:
        input_dim = X_train.shape[1]
        layers = self.config.autoencoder_layers
        model = Autoencoder(input_dim, layers)
        tensor_data = torch.tensor(X_train.values, dtype=torch.float32)
        dataset = TensorDataset(tensor_data, tensor_data)
        loader = DataLoader(dataset, batch_size=self.config.autoencoder_batch_size, shuffle=True)
        optimizer = optim.Adam(model.parameters(), lr=self.config.autoencoder_learning_rate)
        criterion = nn.MSELoss()
        model.train()
        for epoch in range(self.config.autoencoder_epochs):
            epoch_loss = 0.0
            batch_count = 0
            for batch_x, _ in loader:
                optimizer.zero_grad()
                reconstructed = model(batch_x)
                loss = criterion(reconstructed, batch_x)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                batch_count += 1
            if (epoch + 1) % 20 == 0:
                logger.info("Autoencoder epoch %d/%d, loss=%.6f", epoch + 1, self.config.autoencoder_epochs, epoch_loss / max(batch_count, 1))
        model.eval()
        return model

    def train(self, X_train: pd.DataFrame, y_train: Union[pd.Series, np.ndarray]) -> Any:
        logger.info("Training Isolation Forest with contamination=%.4f", self.config.contamination)
        self.isolation_forest = IsolationForest(
            n_estimators=self.config.n_estimators_if,
            max_samples=self.config.max_samples_if,
            max_features=self.config.max_features_if,
            contamination=self.config.contamination,
            random_state=self.config.random_state,
            n_jobs=self.config.n_jobs,
        )
        self.isolation_forest.fit(X_train)
        logger.info("Isolation Forest trained")
        logger.info("Training Autoencoder")
        self.autoencoder_model = self._train_autoencoder(X_train)
        logger.info("Autoencoder trained")
        if self.reference_data is None:
            self.reference_data = X_train.copy()
        self.model = self.isolation_forest
        return self.model

    def _autoencoder_anomaly_score(self, X: pd.DataFrame) -> np.ndarray:
        if self.autoencoder_model is None:
            raise ValueError("Autoencoder not trained")
        tensor_data = torch.tensor(X.values, dtype=torch.float32)
        self.autoencoder_model.eval()
        with torch.no_grad():
            reconstructed = self.autoencoder_model(tensor_data)
        mse = torch.mean((tensor_data - reconstructed) ** 2, dim=1).numpy()
        return mse

    def _ensemble_anomaly_score(self, X: pd.DataFrame) -> np.ndarray:
        if self.isolation_forest is None:
            raise ValueError("Isolation Forest not trained")
        if_score = -self.isolation_forest.decision_function(X)
        if_score = (if_score - if_score.min()) / max(if_score.max() - if_score.min(), 1e-10)
        ae_score = self._autoencoder_anomaly_score(X)
        ae_score = (ae_score - ae_score.min()) / max(ae_score.max() - ae_score.min(), 1e-10)
        ensemble_score = (
            self.config.ensemble_weight_if * if_score
            + self.config.ensemble_weight_ae * ae_score
        )
        return ensemble_score

    def evaluate(self, X_test: pd.DataFrame, y_test: Union[pd.Series, np.ndarray]) -> Dict[str, float]:
        scores = self._ensemble_anomaly_score(X_test)
        predictions = (scores > np.percentile(scores, (1 - self.config.contamination) * 100)).astype(int)
        y_test_arr = np.asarray(y_test)
        metrics: Dict[str, float] = {}
        if len(np.unique(y_test_arr)) > 1:
            from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
            metrics["precision"] = float(precision_score(y_test_arr, predictions, zero_division=0))
            metrics["recall"] = float(recall_score(y_test_arr, predictions, zero_division=0))
            metrics["f1"] = float(f1_score(y_test_arr, predictions, zero_division=0))
            try:
                metrics["roc_auc"] = float(roc_auc_score(y_test_arr, scores))
            except ValueError:
                metrics["roc_auc"] = 0.0
        metrics["anomaly_rate"] = float(predictions.mean())
        metrics["mean_anomaly_score"] = float(scores.mean())
        metrics["std_anomaly_score"] = float(scores.std())
        anomaly_df = pd.DataFrame({
            "anomaly_score": scores,
            "predicted_anomaly": predictions,
            "actual_label": y_test_arr,
        })
        anomaly_path = Path("anomaly_scores.csv")
        anomaly_df.to_csv(anomaly_path, index=False)
        mlflow.log_artifact(str(anomaly_path))
        logger.info("Anomaly detection metrics: %s", json.dumps(metrics, indent=2))
        if self.reference_data is not None:
            drift_metrics = self._detect_drift(X_test)
            metrics.update(drift_metrics)
            logger.info("Drift detection metrics: %s", json.dumps(drift_metrics, indent=2))
        return metrics

    def _detect_drift(self, X_current: pd.DataFrame) -> Dict[str, float]:
        if self.reference_data is None:
            return {}
        drift_metrics: Dict[str, float] = {}
        drift_count = 0
        total_features = 0
        for col in X_current.columns:
            if col not in self.reference_data.columns:
                continue
            ref = self.reference_data[col].dropna().values
            cur = X_current[col].dropna().values
            if len(ref) == 0 or len(cur) == 0:
                continue
            total_features += 1
            try:
                stat, p_value = ks_2samp(ref, cur)
                if p_value < self.config.drift_significance_level:
                    drift_count += 1
            except Exception:
                continue
            try:
                w_dist = wasserstein_distance(ref, cur)
                drift_metrics[f"wasserstein_{col}"] = float(w_dist)
            except Exception:
                continue
        drift_metrics["drift_ratio"] = float(drift_count / max(total_features, 1))
        drift_metrics["drifted_features"] = float(drift_count)
        if len(X_current) >= self.config.drift_detection_window:
            window = X_current.tail(self.config.drift_detection_window)
            scores = self._ensemble_anomaly_score(window)
            drift_metrics["window_anomaly_rate"] = float(
                (scores > np.percentile(scores, 90)).mean()
            )
        return drift_metrics

    def explain(self, X: pd.DataFrame) -> Dict[str, Any]:
        scores = self._ensemble_anomaly_score(X)
        anomaly_indices = np.argsort(scores)[-10:][::-1]
        explanations: Dict[str, Any] = {
            "anomaly_scores": scores[:100].tolist() if len(scores) > 100 else scores.tolist(),
            "top_anomalies": [],
        }
        for idx in anomaly_indices:
            if idx >= len(X):
                continue
            row = X.iloc[idx]
            if self.feature_names is None:
                continue
            contributions = {}
            row_values = row.values
            row_mean = X.values.mean(axis=0)
            for i, fname in enumerate(self.feature_names):
                if i < len(row_values) and i < len(row_mean):
                    contributions[fname] = float(abs(row_values[i] - row_mean[i]))
            sorted_contrib = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:10]
            explanations["top_anomalies"].append({
                "index": int(idx),
                "anomaly_score": float(scores[idx]),
                "contributing_features": dict(sorted_contrib),
            })
            if len(explanations["top_anomalies"]) >= 5:
                break
        logger.info("Anomaly explanations generated for %d samples", len(explanations["top_anomalies"]))
        return explanations

    def save_model(self, path: Optional[str] = None) -> str:
        if path is None:
            path = str(Path("models") / f"anomaly_detector_{self.version}")
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)
        if_model_uri = mlflow.sklearn.log_model(
            sk_model=self.isolation_forest,
            artifact_path="isolation_forest",
            registered_model_name="AnomalyDetector_IF",
            serialization_format="cloudpickle",
        )
        if self.autoencoder_model is not None:
            dummy_input = torch.zeros(1, self.input_dim)
            ae_uri = mlflow.pytorch.log_model(
                pytorch_model=self.autoencoder_model,
                artifact_path="autoencoder",
                registered_model_name="AnomalyDetector_AE",
            )
        config_dict = {
            "version": self.version,
            "feature_names": self.feature_names,
            "input_dim": self.input_dim,
            "contamination": self.config.contamination,
            "ensemble_weights": {
                "if": self.config.ensemble_weight_if,
                "ae": self.config.ensemble_weight_ae,
            },
        }
        params_path = save_path / "pipeline_config.json"
        with open(params_path, "w") as f:
            json.dump(config_dict, f, indent=2, default=str)
        mlflow.log_artifact(str(params_path))
        logger.info("Anomaly detector models saved to %s", if_model_uri.model_uri)
        return if_model_uri.model_uri

    def deploy(self, model_uri: str, stage: str = "Staging") -> Dict[str, Any]:
        client = mlflow.tracking.MlflowClient()
        model_name = "AnomalyDetector"
        try:
            client.create_registered_model(model_name)
        except mlflow.exceptions.MlflowException:
            pass
        version = client.create_model_version(
            name=model_name,
            source=model_uri,
            run_id=mlflow.active_run().info.run_id if mlflow.active_run() else None,
        )
        client.transition_model_version_stage(
            name=model_name, version=version.version, stage=stage
        )
        logger.info("AnomalyDetector model version %s promoted to %s", version.version, stage)
        return {
            "model_name": model_name,
            "version": version.version,
            "stage": stage,
            "model_uri": model_uri,
        }
