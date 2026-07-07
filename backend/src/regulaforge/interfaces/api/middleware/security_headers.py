"""Security headers middleware for CSP, HSTS, and other protections.

Adds Content-Security-Policy, Strict-Transport-Security, and other
security-related HTTP headers to all responses. Configurable via
application settings.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)

# Default Content-Security-Policy (strict but functional)
_DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)

# Development-mode CSP (more permissive for hot-reload)
_DEV_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' ws: http://localhost:* https://fonts.googleapis.com https://fonts.gstatic.com; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to every response.

    Headers applied:
    - Content-Security-Policy (configurable)
    - Strict-Transport-Security (HSTS, production only)
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 0 (deprecated but still scanned)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: minimal set
    """

    def __init__(
        self,
        app: ASGIApp,
        csp: str = "",
        hsts_max_age: int = 31536000,
        hsts_include_subdomains: bool = True,
    ) -> None:
        super().__init__(app)
        self._csp = csp or (_DEV_CSP if settings.is_development() else _DEFAULT_CSP)
        self._hsts = f"max-age={hsts_max_age}" + ("; includeSubDomains" if hsts_include_subdomains else "")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        response.headers["Content-Security-Policy"] = self._csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )

        if settings.environment.value == "production":
            response.headers["Strict-Transport-Security"] = self._hsts

        return response


def add_security_headers_middleware(app: FastAPI) -> None:
    """Register the SecurityHeadersMiddleware on a FastAPI application."""
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware registered")
