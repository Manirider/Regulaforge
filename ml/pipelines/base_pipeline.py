from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union
import logging
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split

from .config import PipelineConfig

logger = logging.getLogger(__name__)


class BaseMLPipeline(ABC):
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._setup_logging()
        self._setup_mlflow()
        self.model: Optional[Any] = None
        self.preprocessor: Optional[Any] = None
        self.feature_names: Optional[List[str]] = None
        self.X_train: Optional[pd.DataFrame] = None
        self.X_test: Optional[pd.DataFrame] = None
        self.y_train: Optional[Union[pd.Series, np.ndarray]] = None
        self.y_test: Optional[Union[pd.Series, np.ndarray]] = None
        self.version: str = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO if self.config.verbose else logging.WARNING,
            format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        )

    def _setup_mlflow(self) -> None:
        if self.config.tracking_uri:
            mlflow.set_tracking_uri(self.config.tracking_uri)
        if self.config.model_registry_uri:
            mlflow.set_registry_uri(self.config.model_registry_uri)
        mlflow.set_experiment(self.config.experiment_name)

    @abstractmethod
    def load_data(self, data_path: str, **kwargs) -> Tuple[pd.DataFrame, Union[pd.Series, np.ndarray]]:
        ...

    @abstractmethod
    def preprocess(
        self, X: pd.DataFrame, y: Optional[Union[pd.Series, np.ndarray]] = None, fit: bool = True
    ) -> Tuple[pd.DataFrame, Optional[Union[pd.Series, np.ndarray]]]:
        ...

    @abstractmethod
    def feature_engineer(self, X: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        ...

    @abstractmethod
    def train(self, X_train: pd.DataFrame, y_train: Union[pd.Series, np.ndarray]) -> Any:
        ...

    @abstractmethod
    def evaluate(
        self, X_test: pd.DataFrame, y_test: Union[pd.Series, np.ndarray]
    ) -> Dict[str, float]:
        ...

    @abstractmethod
    def explain(self, X: pd.DataFrame) -> Dict[str, Any]:
        ...

    @abstractmethod
    def save_model(self, path: Optional[str] = None) -> str:
        ...

    @abstractmethod
    def deploy(self, model_uri: str, stage: str = "Staging") -> Dict[str, Any]:
        ...

    def split_data(
        self,
        X: pd.DataFrame,
        y: Union[pd.Series, np.ndarray],
        stratify: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> None:
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X,
            y,
            test_size=self.config.test_size,
            random_state=self.config.random_state,
            stratify=stratify,
        )
        logger.info(
            "Data split: train=%d, test=%d", len(self.X_train), len(self.X_test)
        )

    def run(
        self, data_path: str, target_col: str = "target", **kwargs
    ) -> Dict[str, Any]:
        with mlflow.start_run(run_name=f"{self.config.experiment_name}_{self.version}"):
            mlflow.log_params(self._flatten_config())
            try:
                logger.info("Loading data from %s", data_path)
                X, y = self.load_data(data_path, target_col=target_col, **kwargs)

                logger.info("Preprocessing data")
                X, y = self.preprocess(X, y, fit=True)

                logger.info("Engineering features")
                X = self.feature_engineer(X, fit=True)

                stratify = y if y.dtype.name != "float64" else None
                self.split_data(X, y, stratify=stratify)

                logger.info("Training model")
                self.model = self.train(self.X_train, self.y_train)

                logger.info("Evaluating model")
                metrics = self.evaluate(self.X_test, self.y_test)
                mlflow.log_metrics(metrics)
                logger.info("Metrics: %s", json.dumps(metrics, indent=2))

                logger.info("Generating explanations")
                explanation = self.explain(self.X_test)
                self._log_explanations(explanation)

                model_uri = self.save_model()
                logger.info("Model saved to %s", model_uri)

                deployment = self.deploy(model_uri)
                logger.info("Deployment: %s", deployment)

                return {
                    "run_id": mlflow.active_run().info.run_id,
                    "version": self.version,
                    "metrics": metrics,
                    "model_uri": model_uri,
                    "deployment": deployment,
                }
            except Exception as exc:
                logger.error("Pipeline run failed: %s", exc, exc_info=True)
                mlflow.log_param("error", str(exc))
                raise
            finally:
                mlflow.end_run()

    def _flatten_config(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key, value in self.config.__dict__.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    params[f"{key}_{sub_key}"] = sub_value
            elif not isinstance(value, (list, tuple)):
                params[key] = value
        return params

    def _log_explanations(self, explanation: Dict[str, Any]) -> None:
        explanation_path = Path("explanations")
        explanation_path.mkdir(exist_ok=True)
        explanation_file = explanation_path / f"explanation_{self.version}.json"
        serializable = {
            k: v if isinstance(v, (str, int, float, bool, list, dict)) else str(v)
            for k, v in explanation.items()
        }
        with open(explanation_file, "w") as f:
            json.dump(serializable, f, indent=2)
        mlflow.log_artifact(str(explanation_file))
        logger.info("Explanations logged to %s", explanation_file)
