from __future__ import annotations

from typing import Optional

from regulaforge.modules.reports.domain.models import Report, ReportSchedule, ReportTemplate


class ReportRepository:
    async def find_by_id(self, report_id: str) -> Optional[Report]:
        raise NotImplementedError

    async def find_all(self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None) -> list[Report]:
        raise NotImplementedError

    async def count(self, tenant_id: Optional[str] = None) -> int:
        raise NotImplementedError

    async def save(self, report: Report) -> Report:
        raise NotImplementedError

    async def delete(self, report_id: str) -> None:
        raise NotImplementedError


class ReportTemplateRepository:
    async def find_by_id(self, template_id: str) -> Optional[ReportTemplate]:
        raise NotImplementedError

    async def find_all(self) -> list[ReportTemplate]:
        raise NotImplementedError

    async def save(self, template: ReportTemplate) -> ReportTemplate:
        raise NotImplementedError


class ReportScheduleRepository:
    async def find_by_id(self, schedule_id: str) -> Optional[ReportSchedule]:
        raise NotImplementedError

    async def find_all(self) -> list[ReportSchedule]:
        raise NotImplementedError

    async def find_due(self) -> list[ReportSchedule]:
        raise NotImplementedError

    async def save(self, schedule: ReportSchedule) -> ReportSchedule:
        raise NotImplementedError
