"""Request context extraction for audit logging.

Separated from AuditMiddleware to follow Single Responsibility Principle.
Handles extracting actor, tenant, and resource information from HTTP requests.
"""

import json
from typing import Any, Optional
from uuid import UUID

from fastapi import Request

from regulaforge.config.constants import AuditAction
from regulaforge.domain.entities.user import User

_METHOD_TO_ACTION: dict[str, AuditAction] = {
    "POST": AuditAction.CREATE,
    "PUT": AuditAction.UPDATE,
    "PATCH": AuditAction.UPDATE,
    "DELETE": AuditAction.DELETE,
}

_DEFAULT_EXCLUDED_PATHS: set[str] = {
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/swagger",
}


class AuditContextExtractor:
    """Extracts audit-relevant context from HTTP requests.

    Responsibilities:
    - Actor identification (authenticated user)
    - Tenant context extraction
    - Resource type and ID parsing from URL path
    - Request body capture for change tracking
    - Change computation for PUT/PATCH methods
    """

    def __init__(self, excluded_paths: Optional[set[str]] = None) -> None:
        self._excluded_paths: set[str] = _DEFAULT_EXCLUDED_PATHS.union(
            excluded_paths or set()
        )

    def should_audit(self, request: Request) -> bool:
        """Determine whether a request should be audited based on method and path."""
        if request.method not in _METHOD_TO_ACTION:
            return False
        path = request.url.path.lower()
        return all(not path.startswith(excluded.lower()) for excluded in self._excluded_paths)

    def get_action(self, method: str) -> AuditAction:
        """Map HTTP method to AuditAction."""
        return _METHOD_TO_ACTION.get(method, AuditAction.UPDATE)

    def extract_actor(self, request: Request) -> Optional[User]:
        """Extract the authenticated user from request state."""
        user = getattr(request.state, "user", None)
        if user is not None:
            return user
        actor = getattr(request.state, "actor", None)
        if actor is not None and isinstance(actor, User):
            return actor
        return None

    def extract_tenant_id(self, request: Request) -> Optional[UUID]:
        """Extract tenant UUID from request state or user context."""
        tenant = getattr(request.state, "tenant", None)
        if tenant is not None and isinstance(tenant, dict):
            tid = tenant.get("id")
            if tid:
                try:
                    return UUID(tid)
                except (ValueError, TypeError):
                    return None
        user = self.extract_actor(request)
        if user is not None and user.tenant_id is not None:
            return user.tenant_id
        return None

    def parse_resource_info(self, request: Request) -> tuple[str, str]:
        """Extract resource type and ID from the URL path."""
        path_segments = [s for s in request.url.path.split("/") if s]
        resource_type = "unknown"
        resource_id = request.url.path

        api_prefix_idx = -1
        for i, segment in enumerate(path_segments):
            if segment in ("api",):
                api_prefix_idx = i
                break

        relevant = (
            path_segments[api_prefix_idx + 1:]
            if api_prefix_idx >= 0
            else path_segments
        )

        if len(relevant) >= 2:
            resource_type = relevant[0]
            resource_id = relevant[1]
        elif len(relevant) == 1:
            resource_type = relevant[0]

        return resource_type, resource_id

    async def capture_body(self, request: Request) -> Optional[str]:
        """Read the request body without consuming it."""
        try:
            body_bytes = await request.body()
            return body_bytes.decode("utf-8") if body_bytes else None
        except Exception:
            return None

    def compute_changes(self, request: Request, body: Optional[str]) -> Optional[dict[str, Any]]:
        """Compute change record for PUT/PATCH requests."""
        if request.method not in ("PUT", "PATCH") or not body:
            return None
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return {"new": parsed}
            return None
        except (json.JSONDecodeError, ValueError):
            return None

    def build_details(
        self,
        request: Request,
        status_code: int,
        duration_ms: float,
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build the details dict for an audit entry."""
        details: dict[str, Any] = {
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.url.query),
            "duration_ms": round(duration_ms, 1),
        }
        if error:
            details["error"] = error
            details["status_code"] = 500
        else:
            details["status_code"] = status_code
        return details
