"""Request/response logging middleware.

Provides structured logging of all API requests with timing,
status codes, and correlation IDs for distributed tracing.
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from regulaforge.config.logging import CorrelationIdFilter, get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for HTTP request/response logging.

    Logs every API request with method, path, status code,
    duration, and correlation ID.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Set correlation ID from header or generate new
        correlation_id = request.headers.get("X-Correlation-ID")
        CorrelationIdFilter.set_correlation_id(correlation_id)

        start_time = time.monotonic()

        # Log request
        logger.info(
            "Request: %s %s",
            request.method,
            request.url.path,
            extra={
                "http_method": request.method,
                "path": request.url.path,
                "query_params": str(request.url.query),
                "client_host": request.client.host if request.client else None,
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Request failed: %s %s (%.1fms)",
                request.method, request.url.path, duration_ms,
                extra={"duration_ms": round(duration_ms, 1)},
                exc_info=True,
            )
            raise

        duration_ms = (time.monotonic() - start_time) * 1000

        # Log response
        logger.info(
            "Response: %s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "http_method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
            },
        )

        return response
