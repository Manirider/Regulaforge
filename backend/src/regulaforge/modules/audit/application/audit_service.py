from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from regulaforge.modules.audit.domain.models import AuditAction, AuditEntry, AuditResource
from regulaforge.modules.audit.domain.repository import AuditRepository

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self._audit_repo = audit_repo

    async def log(
        self,
        actor_id: str,
        action: AuditAction,
        resource: AuditResource,
        resource_id: str = "",
        resource_name: str = "",
        details: Optional[dict[str, Any]] = None,
        actor_email: str = "",
        ip_address: str = "",
        user_agent: str = "",
        tenant_id: str = "",
        changes: Optional[dict[str, Any]] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            resource=resource,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_id=tenant_id,
            changes=changes,
        )
        return await self._audit_repo.save(entry)

    async def get_entry(self, entry_id: str) -> AuditEntry:
        entry = await self._audit_repo.find_by_id(entry_id)
        if not entry:
            from regulaforge.common.exceptions import NotFoundError
            raise NotFoundError(f"Audit entry {entry_id} not found")
        return entry

    async def query(
        self,
        skip: int = 0,
        limit: int = 100,
        actor_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
    ) -> tuple[list[AuditEntry], int]:
        entries = await self._audit_repo.find_all(
            skip=skip,
            limit=limit,
            actor_id=actor_id,
            resource=resource,
            action=action,
            start_date=start_date,
            end_date=end_date,
            tenant_id=tenant_id,
        )
        total = await self._audit_repo.count(
            actor_id=actor_id,
            resource=resource,
            action=action,
            start_date=start_date,
            end_date=end_date,
            tenant_id=tenant_id,
        )
        return entries, total
