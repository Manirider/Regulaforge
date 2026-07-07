"""API middleware package.

Provides middleware components for authentication, authorization,
logging, rate limiting, metrics, error handling, and security headers.
"""

from regulaforge.interfaces.api.middleware.auth_middleware import (
    get_current_user,
    get_current_user_optional,
    get_current_tenant,
    get_token_service,
    require_permission,
    require_role,
)
from regulaforge.interfaces.api.middleware.error_handler import register_error_handlers
from regulaforge.interfaces.api.middleware.logging_middleware import LoggingMiddleware
from regulaforge.interfaces.api.middleware.prometheus_middleware import PrometheusMetricsMiddleware
from regulaforge.interfaces.api.middleware.rate_limit_middleware import RateLimitMiddleware, add_rate_limit_middleware
from regulaforge.interfaces.api.middleware.security_headers import SecurityHeadersMiddleware, add_security_headers_middleware

__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "get_current_tenant",
    "get_token_service",
    "require_permission",
    "require_role",
    "register_error_handlers",
    "LoggingMiddleware",
    "PrometheusMetricsMiddleware",
    "RateLimitMiddleware",
    "add_rate_limit_middleware",
    "SecurityHeadersMiddleware",
    "add_security_headers_middleware",
]
