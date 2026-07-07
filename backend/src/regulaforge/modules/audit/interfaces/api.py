from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from regulaforge.common.exceptions import NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.audit.application.audit_service import AuditService
from regulaforge.modules.audit.domain.models import AuditAction, AuditEntry, AuditResource

logger = logging.getLogger(__name__)


def create_audit_router(
    audit_service: Optional[AuditService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/audit",
        tags=["Audit"],
        dependencies=dependencies or [],
    )

    @router.get("/logs")
    async def query_audit_logs(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        actor_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        entries, total = await audit_service.query(
            skip=skip,
            limit=limit,
            actor_id=actor_id,
            resource=resource,
            action=action,
            start_date=start_date,
            end_date=end_date,
            tenant_id=tenant_id,
        )
        return create_response(data={
            "items": [{
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "actor_id": e.actor_id,
                "actor_email": e.actor_email,
                "action": e.action.value,
                "resource": e.resource.value,
                "resource_id": e.resource_id,
                "resource_name": e.resource_name,
                "details": e.details,
                "ip_address": e.ip_address,
                "changes": e.changes,
            } for e in entries],
            "total": total,
            "skip": skip,
            "limit": limit,
        })

    @router.get("/logs/{entry_id}")
    async def get_audit_entry(entry_id: str) -> dict[str, Any]:
        try:
            entry = await audit_service.get_entry(entry_id)
            return create_response(data={
                "id": entry.id,
                "timestamp": entry.timestamp.isoformat(),
                "actor_id": entry.actor_id,
                "actor_email": entry.actor_email,
                "action": entry.action.value,
                "resource": entry.resource.value,
                "resource_id": entry.resource_id,
                "resource_name": entry.resource_name,
                "details": entry.details,
                "ip_address": entry.ip_address,
                "user_agent": entry.user_agent,
                "changes": entry.changes,
                "metadata": entry.metadata,
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return router
