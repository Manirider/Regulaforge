"""FastAPI middleware for automatic audit logging of HTTP requests.

Intercepts mutating HTTP methods (POST, PUT, PATCH, DELETE) and
persists audit entries capturing who did what to which resource.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from regulaforge.audit.application.audit_service import AuditService
from regulaforge.audit.interfaces.context_extractor import AuditContextExtractor
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that automatically audits state-changing requests.

    Delegates context extraction to AuditContextExtractor and
    persistence to AuditService, following Single Responsibility.
    """

    def __init__(
        self,
        app: ASGIApp,
        excluded_paths: Optional[list[str]] = None,
    ) -> None:
        super().__init__(app)
        self._extractor = AuditContextExtractor(
            excluded_paths=set(excluded_paths) if excluded_paths else None
        )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self._extractor.should_audit(request):
            return await call_next(request)

        start_time = time.monotonic()
        body = await self._extractor.capture_body(request)

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            await self._log_failure(request, exc, duration_ms)
            raise

        duration_ms = (time.monotonic() - start_time) * 1000

        if 200 <= response.status_code < 500:
            await self._log_audit_entry(request, response, body, duration_ms)

        return response

    async def _log_audit_entry(
        self,
        request: Request,
        response: Response,
        body: Optional[str],
        duration_ms: float,
    ) -> None:
        try:
            session = request.state.db_session
        except AttributeError:
            logger.warning("No database session in request state; skipping audit")
            return

        actor = self._extractor.extract_actor(request)
        if actor is None:
            logger.debug("No authenticated actor; skipping audit")
            return

        tenant_id = self._extractor.extract_tenant_id(request)
        if tenant_id is None:
            logger.debug("No tenant context; skipping audit")
            return

        action = self._extractor.get_action(request.method)
        resource_type, resource_id = self._extractor.parse_resource_info(request)
        changes = self._extractor.compute_changes(request, body)
        correlation_id = request.headers.get("X-Correlation-ID")
        details = self._extractor.build_details(request, response.status_code, duration_ms)

        audit_service = AuditService(session)
        await audit_service.log_action(
            action=action,
            actor_id=actor.id,
            actor_email=actor.email,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            changes=changes,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            correlation_id=correlation_id,
        )

    async def _log_failure(
        self,
        request: Request,
        exc: Exception,
        duration_ms: float,
    ) -> None:
        try:
            session = request.state.db_session
        except AttributeError:
            return

        actor = self._extractor.extract_actor(request)
        if actor is None:
            return

        tenant_id = self._extractor.extract_tenant_id(request)
        if tenant_id is None:
            return

        action = self._extractor.get_action(request.method)
        resource_type, resource_id = self._extractor.parse_resource_info(request)
        details = self._extractor.build_details(request, 500, duration_ms, error=str(exc))

        audit_service = AuditService(session)
        await audit_service.log_action(
            action=action,
            actor_id=actor.id,
            actor_email=actor.email,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )


def add_audit_middleware(
    app: FastAPI,
    excluded_paths: Optional[list[str]] = None,
) -> None:
    """Register the AuditMiddleware on a FastAPI application."""
    app.add_middleware(AuditMiddleware, excluded_paths=excluded_paths)
    logger.info(
        "Audit middleware registered (excluded_paths=%s)",
        excluded_paths or [],
    )
