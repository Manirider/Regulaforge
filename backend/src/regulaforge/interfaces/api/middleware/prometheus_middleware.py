"""Prometheus HTTP metrics middleware.

Instruments all HTTP requests with duration, count, and concurrency
metrics exposed at the /metrics endpoint for Prometheus scraping.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from regulaforge.infrastructure.monitoring.metrics import (
    active_requests,
    http_request_duration_seconds,
    http_requests_total,
)

EXCLUDED_PATHS = {"/metrics", "/health", "/api/v1/metrics", "/api/v1/health"}


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP request metrics for Prometheus."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        active_requests.inc()
        start_time = time.monotonic()
        method = request.method
        endpoint = request.url.path

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        except Exception:
            status_code = "500"
            raise
        finally:
            elapsed = time.monotonic() - start_time
            active_requests.dec()

            http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(elapsed)
