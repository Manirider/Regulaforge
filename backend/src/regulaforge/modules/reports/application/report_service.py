from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from regulaforge.common.exceptions import NotFoundError
from regulaforge.modules.reports.domain.models import Report, ReportFormat, ReportSchedule, ReportTemplate
from regulaforge.modules.reports.domain.repository import (
    ReportRepository,
    ReportScheduleRepository,
    ReportTemplateRepository,
)

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(
        self,
        report_repo: ReportRepository,
        template_repo: ReportTemplateRepository,
        schedule_repo: ReportScheduleRepository,
    ) -> None:
        self._report_repo = report_repo
        self._template_repo = template_repo
        self._schedule_repo = schedule_repo

    async def get_report(self, report_id: str) -> Report:
        report = await self._report_repo.find_by_id(report_id)
        if not report:
            raise NotFoundError(f"Report {report_id} not found")
        return report

    async def list_reports(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> tuple[list[Report], int]:
        reports = await self._report_repo.find_all(skip, limit, tenant_id)
        total = await self._report_repo.count(tenant_id)
        return reports, total

    async def create_report(self, report: Report) -> Report:
        report.status = "pending"
        return await self._report_repo.save(report)

    async def generate_report(self, report_id: str) -> Report:
        report = await self.get_report(report_id)
        report.status = "generating"
        await self._report_repo.save(report)

        try:
            report.data = await self._build_report_data(report)
            report.status = "completed"
            report.generated_at = datetime.utcnow()
        except Exception as exc:
            report.status = "failed"
            report.data = {"error": str(exc)}

        return await self._report_repo.save(report)

    async def delete_report(self, report_id: str) -> None:
        report = await self.get_report(report_id)
        await self._report_repo.delete(report_id)

    async def get_template(self, template_id: str) -> ReportTemplate:
        template = await self._template_repo.find_by_id(template_id)
        if not template:
            raise NotFoundError(f"Report template {template_id} not found")
        return template

    async def list_templates(self) -> list[ReportTemplate]:
        return await self._template_repo.find_all()

    async def create_template(self, template: ReportTemplate) -> ReportTemplate:
        return await self._template_repo.save(template)

    async def create_schedule(self, schedule: ReportSchedule) -> ReportSchedule:
        return await self._schedule_repo.save(schedule)

    async def list_schedules(self) -> list[ReportSchedule]:
        return await self._schedule_repo.find_all()

    async def _build_report_data(self, report: Report) -> dict[str, Any]:
        return {
            "report_id": report.id,
            "title": report.title,
            "type": report.report_type,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": f"Report '{report.title}' generated",
            "metrics": {},
        }
