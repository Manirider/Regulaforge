from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response

from regulaforge.common.exceptions import NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.reports.application.report_service import ReportService
from regulaforge.modules.reports.domain.models import Report, ReportSchedule, ReportTemplate

logger = logging.getLogger(__name__)


def create_reports_router(
    report_service: Optional[ReportService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/reports",
        tags=["Reports"],
        dependencies=dependencies or [],
    )

    @router.get("")
    async def list_reports(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        reports, total = await report_service.list_reports(skip, limit, tenant_id)
        return create_response(data={
            "items": [{
                "id": r.id,
                "title": r.title,
                "report_type": r.report_type,
                "format": r.format.value,
                "status": r.status,
                "file_url": r.file_url,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            } for r in reports],
            "total": total,
        })

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def create_report(body: Report) -> dict[str, Any]:
        report = await report_service.create_report(body)
        return create_response(data={"id": report.id, "status": report.status})

    @router.get("/{report_id}")
    async def get_report(report_id: str) -> dict[str, Any]:
        try:
            report = await report_service.get_report(report_id)
            return create_response(data={
                "id": report.id,
                "title": report.title,
                "description": report.description,
                "report_type": report.report_type,
                "format": report.format.value,
                "status": report.status,
                "data": report.data,
                "filters": report.filters,
                "file_url": report.file_url,
                "generated_by": report.generated_by,
                "created_at": report.created_at.isoformat(),
                "generated_at": report.generated_at.isoformat() if report.generated_at else None,
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/{report_id}/generate")
    async def generate_report(report_id: str) -> dict[str, Any]:
        try:
            report = await report_service.generate_report(report_id)
            return create_response(data={"id": report.id, "status": report.status})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_report(report_id: str) -> Response:
        try:
            await report_service.delete_report(report_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.get("/templates")
    async def list_templates() -> dict[str, Any]:
        templates = await report_service.list_templates()
        return create_response(data=[{
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "output_format": t.output_format.value,
        } for t in templates])

    @router.post("/templates", status_code=status.HTTP_201_CREATED)
    async def create_template(body: ReportTemplate) -> dict[str, Any]:
        template = await report_service.create_template(body)
        return create_response(data={"id": template.id, "name": template.name})

    @router.get("/schedules")
    async def list_schedules() -> dict[str, Any]:
        schedules = await report_service.list_schedules()
        return create_response(data=[{
            "id": s.id,
            "report_template_id": s.report_template_id,
            "cron_expression": s.cron_expression,
            "enabled": s.enabled,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        } for s in schedules])

    @router.post("/schedules", status_code=status.HTTP_201_CREATED)
    async def create_schedule(body: ReportSchedule) -> dict[str, Any]:
        schedule = await report_service.create_schedule(body)
        return create_response(data={"id": schedule.id})

    return router
