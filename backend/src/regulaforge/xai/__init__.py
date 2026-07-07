"""RegulaForge Explainable AI (XAI) Subsystem.

Provides human-understandable explanations for all AI decisions in the
compliance platform, supporting SHAP, LIME, counterfactual explanations,
and natural language explanations.

Clean Architecture layers:
    domain      → Pure domain models, enums, events
    application → Explainer services, orchestration
    infrastructure → Persistence, visualization, caching
    interfaces  → FastAPI endpoints, CLI commands
"""

from regulaforge.config.logging import get_logger

logger = get_logger(__name__)
logger.info("XAI subsystem loaded")

__all__: list[str] = []
