from typing import Any, Dict, List, Optional, Tuple, Union
import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
import shap
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import GridSearchCV

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None  # type: ignore

from .base_pipeline import BaseMLPipeline
from .config import RiskScoringConfig

logger = logging.getLogger(__name__)


class RiskScorerPipeline(BaseMLPipeline):
    def __init__(self, config: Optional[RiskScoringConfig] = None):
        super().__init__(config or RiskScoringConfig())
        self.config: RiskScoringConfig = self.config
        self.scaler: Optional[StandardScaler] = None
        self.label_encoders: Dict[str, LabelEncoder] = {}
        self.categorical_cols: List[str] = []
        self.numeric_cols: List[str] = []
        self.quantile_models: Dict[float, Any] = {}

    def load_data(self, data_path: str, **kwargs) -> Tuple[pd.DataFrame, Union[pd.Series, np.ndarray]]:
        target_col = kwargs.get("target_col", "risk_score")
        df = pd.read_csv(data_path)
        logger.info("Loaded %d rows with %d columns", len(df), len(df.columns))
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in data")
        y = df.pop(target_col).values.astype(float)
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
                    df[col] = df[col].map(lambda v: v if v in le.classes_ else "MISSING")
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
        risk_interaction_cols = [c for c in df.columns if "risk" in c.lower() or "score" in c.lower()]
        if risk_interaction_cols and len(risk_interaction_cols) >= 2:
            for i in range(len(risk_interaction_cols)):
                for j in range(i + 1, len(risk_interaction_cols)):
                    col_name = f"{risk_interaction_cols[i]}_x_{risk_interaction_cols[j]}"
                    df[col_name] = df[risk_interaction_cols[i]] * df[risk_interaction_cols[j]]
        poly_cols = self.numeric_cols[:min(5, len(self.numeric_cols))]
        for col in poly_cols:
            df[f"{col}_squared"] = df[col] ** 2
            df[f"{col}_cubed"] = df[col] ** 3
        if fit:
            self.feature_names = df.columns.tolist()
        return df

    def _train_quantile_model(self, alpha: float, X_train: pd.DataFrame, y_train: np.ndarray) -> Any:
        if XGBRegressor is None:
            raise ImportError("XGBoost is required for RiskScorerPipeline quantile regression")
        model = XGBRegressor(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            subsample=self.config.subsample,
            min_child_weight=self.config.min_child_weight,
            reg_lambda=self.config.reg_lambda,
            reg_alpha=self.config.reg_alpha,
            objective="reg:quantileerror",
            quantile_alpha=alpha,
            random_state=self.config.random_state,
            n_jobs=self.config.n_jobs,
        )
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_train, y_train)],
            verbose=False,
        )
        logger.info("Quantile model for alpha=%.2f trained", alpha)
        return model

    def train(self, X_train: pd.DataFrame, y_train: Union[pd.Series, np.ndarray]) -> Any:
        y_train_arr = np.asarray(y_train).ravel()
        self.quantile_models = {}
        for alpha in self.config.quantile_alphas:
            model = self._train_quantile_model(alpha, X_train, y_train_arr)
            self.quantile_models[alpha] = model
        if 0.5 in self.quantile_models:
            self.model = self.quantile_models[0.5]
        else:
            self.model = list(self.quantile_models.values())[0]
        return self.model

    def evaluate(self, X_test: pd.DataFrame, y_test: Union[pd.Series, np.ndarray]) -> Dict[str, float]:
        y_test_arr = np.asarray(y_test).ravel()
        y_pred = self.predict_median(X_test)
        metrics: Dict[str, float] = {}
        metrics["mae"] = float(mean_absolute_error(y_test_arr, y_pred))
        metrics["rmse"] = float(np.sqrt(mean_squared_error(y_test_arr, y_pred)))
        metrics["r2"] = float(r2_score(y_test_arr, y_pred))
        residuals = y_test_arr - y_pred
        metrics["max_error"] = float(np.max(np.abs(residuals)))
        metrics["mape"] = float(
            np.mean(np.abs(residuals / (y_test_arr + 1e-10))) * 100
        )
        lower = self.predict_quantile(X_test, self.config.quantile_alphas[0])
        upper = self.predict_quantile(X_test, self.config.quantile_alphas[-1])
        within_interval = float(np.mean((y_test_arr >= lower) & (y_test_arr <= upper)))
        metrics["prediction_interval_coverage"] = within_interval
        logger.info("RiskScorer metrics: %s", json.dumps(metrics, indent=2))
        calibration_data = pd.DataFrame({
            "actual": y_test_arr,
            "predicted": y_pred,
            "lower": lower,
            "upper": upper,
        })
        cal_path = Path("calibration_curve_data.csv")
        calibration_data.to_csv(cal_path, index=False)
        mlflow.log_artifact(str(cal_path))
        return metrics

    def predict_quantile(self, X: pd.DataFrame, alpha: float) -> np.ndarray:
        if alpha not in self.quantile_models:
            raise ValueError(f"Quantile model for alpha={alpha} not trained. Available: {list(self.quantile_models.keys())}")
        return self.quantile_models[alpha].predict(X)

    def predict_median(self, X: pd.DataFrame) -> np.ndarray:
        return self.predict_quantile(X, 0.5)

    def predict_interval(self, X: pd.DataFrame) -> np.ndarray:
        lower = self.predict_quantile(X, self.config.quantile_alphas[0])
        upper = self.predict_quantile(X, self.config.quantile_alphas[-1])
        return np.column_stack([lower, upper])

    def explain(self, X: pd.DataFrame) -> Dict[str, Any]:
        median_model = self.quantile_models.get(0.5, list(self.quantile_models.values())[0])
        try:
            explainer = shap.TreeExplainer(median_model, X, feature_names=self.feature_names)
            shap_values = explainer(X)
            feature_importance = np.abs(shap_values.values).mean(axis=0)
            top_indices = np.argsort(feature_importance)[-20:][::-1]
            top_features = {
                self.feature_names[i]: float(feature_importance[i])
                for i in top_indices
                if i < len(self.feature_names)
            }
            for alpha, model in self.quantile_models.items():
                if alpha != 0.5:
                    try:
                        shaps = explainer(model.predict, X)
                        dep_path = Path(f"shap_dependence_alpha_{alpha}.png")
                        shap.dependence_plot(
                            top_indices[0] if len(top_indices) > 0 else 0,
                            shaps.values,
                            X,
                            show=False,
                        )
                        import matplotlib.pyplot as plt
                        plt.savefig(str(dep_path), bbox_inches="tight")
                        plt.close()
                        mlflow.log_artifact(str(dep_path))
                    except Exception:
                        logger.warning("SHAP dependence plot failed for alpha=%s", alpha, exc_info=True)
            return {
                "feature_importance": top_features,
                "shap_values_shape": list(shap_values.values.shape),
                "explanation_method": "shap_tree",
            }
        except Exception as exc:
            logger.warning("SHAP explanation failed: %s", exc)
            return {"feature_importance": {}, "explanation_method": "shap_tree", "error": str(exc)}

    def save_model(self, path: Optional[str] = None) -> str:
        if path is None:
            path = str(Path("models") / f"risk_scorer_{self.version}")
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)
        mlflow.log_param("quantile_models_trained", list(self.quantile_models.keys()))
        median_uri = mlflow.sklearn.log_model(
            sk_model=self.quantile_models.get(0.5, list(self.quantile_models.values())[0]),
            artifact_path="risk_scorer_median",
            registered_model_name="RiskScorer",
            serialization_format="cloudpickle",
        )
        for alpha, model in self.quantile_models.items():
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path=f"risk_scorer_quantile_{alpha}",
                registered_model_name=f"RiskScorer_Quantile_{alpha}",
                serialization_format="cloudpickle",
            )
        config_dict = {
            "version": self.version,
            "feature_names": self.feature_names,
            "quantile_alphas": self.config.quantile_alphas,
        }
        params_path = save_path / "pipeline_config.json"
        with open(params_path, "w") as f:
            json.dump(config_dict, f, indent=2, default=str)
        mlflow.log_artifact(str(params_path))
        logger.info("Risk scorer model saved to %s", median_uri.model_uri)
        return median_uri.model_uri

    def deploy(self, model_uri: str, stage: str = "Staging") -> Dict[str, Any]:
        client = mlflow.tracking.MlflowClient()
        model_name = "RiskScorer"
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
        logger.info("RiskScorer model version %s promoted to %s", version.version, stage)
        return {
            "model_name": model_name,
            "version": version.version,
            "stage": stage,
            "model_uri": model_uri,
        }
