"""Configuration package for RegulaForge.

Sub-modules:
    settings — Pydantic-settings based application configuration
    logging — Structured JSON logging with context propagation
    constants — Application-wide constants and enumerations
    secrets — Provider-agnostic secrets management
"""

from regulaforge.config.settings import settings

__all__ = ["settings"]

