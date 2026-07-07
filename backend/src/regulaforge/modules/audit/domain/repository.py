from __future__ import annotations

from datetime import datetime
from typing import Optional

from regulaforge.modules.audit.domain.models import AuditEntry


class AuditRepository:
    async def find_by_id(self, entry_id: str) -> Optional[AuditEntry]:
        raise NotImplementedError

    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        actor_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
    ) -> list[AuditEntry]:
        raise NotImplementedError

    async def count(
        self,
        actor_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
    ) -> int:
        raise NotImplementedError

    async def save(self, entry: AuditEntry) -> AuditEntry:
        raise NotImplementedError
