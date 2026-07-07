import argparse
import logging
import os
import json
from pathlib import Path

import mlflow

from pipelines.risk_scorer import RiskScorerPipeline
from pipelines.config import RiskScoringConfig

logger = logging.getLogger(__name__)


def load_config_from_env(config: RiskScoringConfig) -> RiskScoringConfig:
    env_prefix = "RFR_"
    for field_name in config.__dataclass_fields__:
        env_key = f"{env_prefix}{field_name.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            field_type = config.__dataclass_fields__[field_name].type
            if field_type is bool:
                setattr(config, field_name, env_val.lower() in ("true", "1", "yes"))
            elif field_type is int:
                setattr(config, field_name, int(env_val))
            elif field_type is float:
                setattr(config, field_name, float(env_val))
            elif "List" in str(field_type) or "list" in str(field_type):
                import ast
                setattr(config, field_name, ast.literal_eval(env_val))
            else:
                setattr(config, field_name, env_val)
            logger.info("Config override from env: %s = %s", field_name, env_val)
    return config


def load_config_from_file(path: str) -> RiskScoringConfig:
    with open(path) as f:
        data = json.load(f)
    config = RiskScoringConfig(**{
        k: v for k, v in data.items()
        if k in RiskScoringConfig.__dataclass_fields__
    })
    logger.info("Config loaded from file: %s", path)
    return config


def main():
    parser = argparse.ArgumentParser(description="Run Risk Scorer Pipeline")
    parser.add_argument("--data-path", type=str, required=True, help="Path to training data CSV")
    parser.add_argument("--target-col", type=str, default="risk_score", help="Name of target column")
    parser.add_argument("--config-file", type=str, default=None, help="Path to JSON config file")
    parser.add_argument("--tracking-uri", type=str, default=None, help="MLflow tracking URI")
    parser.add_argument("--registry-uri", type=str, default=None, help="MLflow registry URI")
    parser.add_argument("--experiment-name", type=str, default=None, help="MLflow experiment name")
    parser.add_argument("--random-state", type=int, default=None, help="Random seed")
    parser.add_argument("--test-size", type=float, default=None, help="Test set proportion")
    parser.add_argument("--cv-folds", type=int, default=None, help="Cross-validation folds")
    parser.add_argument("--output", type=str, default="risk_scoring_results.json", help="Output results path")
    args = parser.parse_args()

    if args.config_file:
        config = load_config_from_file(args.config_file)
    else:
        config = RiskScoringConfig()

    config = load_config_from_env(config)

    if args.tracking_uri:
        config.tracking_uri = args.tracking_uri
    if args.registry_uri:
        config.model_registry_uri = args.registry_uri
    if args.experiment_name:
        config.experiment_name = args.experiment_name
    if args.random_state is not None:
        config.random_state = args.random_state
    if args.test_size is not None:
        config.test_size = args.test_size
    if args.cv_folds is not None:
        config.cv_folds = args.cv_folds

    logger.info("RiskScoringConfig: %s", config)

    pipeline = RiskScorerPipeline(config=config)
    results = pipeline.run(data_path=args.data_path, target_col=args.target_col)

    results["config"] = {
        k: str(v) if not isinstance(v, (int, float, bool, str, list, dict)) else v
        for k, v in config.__dict__.items()
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info("Results saved to %s", output_path)
    logger.info("Run ID: %s", results.get("run_id"))
    logger.info("Model URI: %s", results.get("model_uri"))

    active_run = mlflow.active_run()
    if active_run:
        mlflow.end_run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    main()
