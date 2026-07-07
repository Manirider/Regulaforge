from typing import Any, Dict, List, Optional, Tuple
import logging
from datetime import datetime

import mlflow
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException

logger = logging.getLogger(__name__)


class ModelRegistry:
    MANAGED_STAGES = ["None", "Staging", "Production", "Archived"]

    def __init__(self, registry_uri: Optional[str] = None, tracking_uri: Optional[str] = None):
        if registry_uri:
            mlflow.set_registry_uri(registry_uri)
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        self.client = MlflowClient()

    def register_model(
        self,
        name: str,
        version: Optional[str] = None,
        source_uri: Optional[str] = None,
        run_id: Optional[str] = None,
        metrics: Optional[Dict[str, float]] = None,
        params: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        try:
            self.client.create_registered_model(name)
            logger.info("Created registered model '%s'", name)
        except MlflowException:
            logger.info("Registered model '%s' already exists", name)
        if source_uri:
            mv = self.client.create_model_version(
                name=name,
                source=source_uri,
                run_id=run_id,
                tags=tags,
            )
            version_str = mv.version
            logger.info("Created model version %s for '%s'", version_str, name)
        else:
            existing = self.client.search_model_versions(f"name='{name}'")
            version_str = version or str(len(existing) + 1)
        if metrics:
            for metric_name, metric_value in metrics.items():
                self.client.log_metric(run_id or "", metric_name, metric_value)
        if params:
            self.client.log_params(run_id or "", params)
        return {
            "name": name,
            "version": version_str,
            "source_uri": source_uri,
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
        }

    def get_model(self, name: str, version: Optional[str] = None, stage: Optional[str] = None) -> Dict[str, Any]:
        if stage and stage in self.MANAGED_STAGES:
            versions = self.client.get_latest_versions(name, stages=[stage])
            if not versions:
                raise ValueError(f"No model '{name}' found in stage '{stage}'")
            mv = versions[0]
        elif version:
            mv = self.client.get_model_version(name, version)
        else:
            versions = self.client.get_latest_versions(name, stages=["None"])
            if not versions:
                raise ValueError(f"No versions found for model '{name}'")
            mv = versions[0]
        return {
            "name": mv.name,
            "version": mv.version,
            "stage": mv.current_stage,
            "status": mv.status,
            "run_id": mv.run_id,
            "source": mv.source,
            "tags": mv.tags,
            "creation_timestamp": mv.creation_timestamp,
        }

    def list_models(
        self,
        filter_criteria: Optional[Dict[str, str]] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        registered_models = self.client.search_registered_models(max_results=max_results)
        results: List[Dict[str, Any]] = []
        for rm in registered_models:
            if filter_criteria:
                name_filter = filter_criteria.get("name", "")
                tag_filter = filter_criteria.get("tags", {})
                if name_filter and name_filter not in rm.name:
                    continue
                if tag_filter and not all(
                    rm.tags.get(k) == v for k, v in tag_filter.items()
                ):
                    continue
            versions = self.client.search_model_versions(f"name='{rm.name}'")
            latest_version = max((int(v.version) for v in versions), default=0)
            stage_counts: Dict[str, int] = {}
            for v in versions:
                stage_counts[v.current_stage] = stage_counts.get(v.current_stage, 0) + 1
            results.append({
                "name": rm.name,
                "latest_version": latest_version,
                "num_versions": len(versions),
                "stages": stage_counts,
                "description": rm.description,
                "tags": rm.tags,
                "creation_timestamp": rm.creation_timestamp,
            })
        return results

    def promote_model(self, name: str, from_stage: str, to_stage: str) -> Dict[str, Any]:
        if from_stage not in self.MANAGED_STAGES:
            raise ValueError(f"Invalid from_stage '{from_stage}'. Must be one of {self.MANAGED_STAGES}")
        if to_stage not in self.MANAGED_STAGES:
            raise ValueError(f"Invalid to_stage '{to_stage}'. Must be one of {self.MANAGED_STAGES}")
        if from_stage == to_stage:
            raise ValueError(f"from_stage and to_stage are both '{from_stage}'")
        current_versions = self.client.get_latest_versions(name, stages=[from_stage])
        if not current_versions:
            raise ValueError(f"No models in stage '{from_stage}' for '{name}'")
        promoted: List[Dict[str, str]] = []
        for mv in current_versions:
            self.client.transition_model_version_stage(
                name=name,
                version=mv.version,
                stage=to_stage,
            )
            if to_stage == "Production":
                for other in self.client.get_latest_versions(name, stages=["Production"]):
                    if other.version != mv.version:
                        self.client.transition_model_version_stage(
                            name=name,
                            version=other.version,
                            stage="Archived",
                        )
                        promoted.append({
                            "version": other.version,
                            "from_stage": "Production",
                            "to_stage": "Archived",
                        })
            promoted.append({
                "version": mv.version,
                "from_stage": from_stage,
                "to_stage": to_stage,
            })
        return {"model_name": name, "promotions": promoted}

    def compare_models(self, name: str, versions: Optional[List[str]] = None) -> Dict[str, Any]:
        all_versions = self.client.search_model_versions(f"name='{name}'")
        if versions:
            all_versions = [v for v in all_versions if v.version in versions]
        if not all_versions:
            raise ValueError(f"No versions found for model '{name}'")
        comparison: Dict[str, Any] = {
            "model_name": name,
            "versions": [],
            "metrics_comparison": {},
            "best_version": None,
        }
        all_metrics: Dict[str, Dict[str, float]] = {}
        for mv in all_versions:
            vinfo: Dict[str, Any] = {
                "version": mv.version,
                "stage": mv.current_stage,
                "status": mv.status,
                "run_id": mv.run_id,
                "source": mv.source,
                "creation_timestamp": mv.creation_timestamp,
            }
            if mv.run_id:
                try:
                    run = self.client.get_run(mv.run_id)
                    vinfo["metrics"] = run.data.metrics
                    vinfo["params"] = run.data.params
                    for metric_name, metric_value in run.data.metrics.items():
                        if metric_name not in all_metrics:
                            all_metrics[metric_name] = {}
                        all_metrics[metric_name][mv.version] = metric_value
                except Exception:
                    logger.warning("Could not fetch run data for version %s", mv.version)
            comparison["versions"].append(vinfo)
        metric_summary: Dict[str, Any] = {}
        best_overall: Optional[Tuple[str, str, float]] = None
        for metric_name, version_values in all_metrics.items():
            values = list(version_values.values())
            if not values:
                continue
            higher_is_better = metric_name not in ("mae", "rmse", "max_error", "mape", "loss")
            best_v = max(version_values, key=version_values.get) if higher_is_better else min(version_values, key=version_values.get)
            best_val = version_values[best_v]
            metric_summary[metric_name] = {
                "values": {v: round(val, 6) for v, val in version_values.items()},
                "best_version": best_v,
                "best_value": best_val,
                "higher_is_better": higher_is_better,
            }
            if higher_is_better and (best_overall is None or best_val > best_overall[2]):
                best_overall = (metric_name, best_v, best_val)
        comparison["metrics_comparison"] = metric_summary
        if best_overall:
            comparison["best_version"] = {
                "version": best_overall[1],
                "deciding_metric": best_overall[0],
                "value": best_overall[2],
            }
        return comparison

    def delete_model(self, name: str, version: Optional[str] = None) -> Dict[str, Any]:
        if version:
            self.client.delete_model_version(name=name, version=version)
            logger.info("Deleted model '%s' version %s", name, version)
            return {"name": name, "version": version, "action": "deleted_version"}
        else:
            self.client.delete_registered_model(name=name)
            logger.info("Deleted registered model '%s' and all versions", name)
            return {"name": name, "action": "deleted_model"}

    def search_models(
        self,
        query: str = "",
        order_by: Optional[List[str]] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        order_by = order_by or ["name ASC"]
        models = self.client.search_registered_models(
            filter_string=query,
            order_by=order_by,
            max_results=max_results,
        )
        results = []
        for rm in models:
            results.append({
                "name": rm.name,
                "tags": rm.tags,
                "description": rm.description,
                "creation_timestamp": rm.creation_timestamp,
            })
        return results
