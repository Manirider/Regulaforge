"""Interface layer for the XAI subsystem.

Provides RESTful API endpoints for generating, retrieving, and
comparing explanations of AI model predictions.
"""

from regulaforge.xai.interfaces.api import router

__all__ = ["router"]
