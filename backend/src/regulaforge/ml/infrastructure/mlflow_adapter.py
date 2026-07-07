from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MLflowAdapter:
    def __init__(self, tracking_uri: Optional[str] = None, experiment_name: str = "regulaforge") -> None:
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self._active_run: Any = None

    def start_run(self, run_name: Optional[str] = None) -> Optional[str]:
        try:
            import mlflow
            if self.tracking_uri:
                mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment_name)
            run = mlflow.start_run(run_name=run_name)
            self._active_run = run
            return run.info.run_id
        except ImportError:
            logger.warning("mlflow not installed, skipping tracking")
            return None
        except Exception as exc:
            logger.warning("Could not start MLflow run: %s", exc)
            return None

    def log_params(self, params: dict[str, Any]) -> None:
        try:
            import mlflow
            mlflow.log_params(params)
        except Exception as exc:
            logger.debug("Could not log params to MLflow: %s", exc)

    def log_metrics(self, metrics: dict[str, float], step: Optional[int] = None) -> None:
        try:
            import mlflow
            mlflow.log_metrics(metrics, step=step)
        except Exception as exc:
            logger.debug("Could not log metrics to MLflow: %s", exc)

    def log_model(
        self,
        model: Any,
        artifact_path: str = "model",
        model_type: Optional[str] = None,
        _input_schema: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        try:
            import mlflow
            if model_type == "xgboost":
                mlflow.xgboost.log_model(model, artifact_path)
            elif model_type == "catboost":
                with tempfile.TemporaryDirectory() as tmpdir:
                    model_path = Path(tmpdir) / "model.cbm"
                    model.save_model(str(model_path))
                    mlflow.log_artifact(str(model_path), artifact_path)
            elif model_type == "lightgbm":
                mlflow.lightgbm.log_model(model, artifact_path)
            else:
                mlflow.sklearn.log_model(model, artifact_path)
            return f"runs:/{self._active_run.info.run_id}/{artifact_path}" if self._active_run else None
        except Exception as exc:
            logger.debug("Could not log model to MLflow: %s", exc)
            return None

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None) -> None:
        try:
            import mlflow
            mlflow.log_artifact(local_path, artifact_path)
        except Exception as exc:
            logger.debug("Could not log artifact to MLflow: %s", exc)

    def log_dict(self, dictionary: dict[str, Any], artifact_file: str) -> None:
        try:
            import mlflow
            mlflow.log_dict(dictionary, artifact_file)
        except Exception as exc:
            logger.debug("Could not log dict to MLflow: %s", exc)

    def end_run(self, status: str = "FINISHED") -> None:
        try:
            import mlflow
            mlflow.end_run(status=status)
        except Exception as exc:
            logger.debug("Could not end MLflow run: %s", exc)
        self._active_run = None

    def register_model(self, model_uri: str, name: str) -> Optional[Any]:
        try:
            import mlflow
            result = mlflow.register_model(model_uri, name)
            logger.info("Registered model %s version %s", name, result.version)
            return result
        except Exception as exc:
            logger.warning("Could not register model %s: %s", name, exc)
            return None

    def load_model(self, model_uri: str) -> Any:
        try:
            import mlflow
            return mlflow.pyfunc.load_model(model_uri)
        except Exception as exc:
            raise RuntimeError(f"Could not load model from {model_uri}: {exc}") from exc

    def search_runs(
        self,
        experiment_name: Optional[str] = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        try:
            import mlflow
            from mlflow.entities import ViewType

            exp_name = experiment_name or self.experiment_name
            experiment = mlflow.get_experiment_by_name(exp_name)
            if experiment is None:
                return []
            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                run_view_type=ViewType.ACTIVE_ONLY,
                max_results=max_results,
            )
            return runs.to_dict("records") if hasattr(runs, "to_dict") else []
        except Exception as exc:
            logger.debug("Could not search MLflow runs: %s", exc)
            return []
