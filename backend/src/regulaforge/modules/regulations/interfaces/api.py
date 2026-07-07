from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response

from regulaforge.common.exceptions import ConflictError, NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.regulations.application.regulation_service import RegulationService
from regulaforge.modules.regulations.domain.models import (
    Assessment,
    ComplianceRequirement,
    Regulation,
    RegulationStatus,
)

logger = logging.getLogger(__name__)


def create_regulations_router(
    regulation_service: Optional[RegulationService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/regulations",
        tags=["Regulations"],
        dependencies=dependencies or [],
    )

    @router.get("")
    async def list_regulations(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        regulations, total = await regulation_service.list_regulations(skip, limit, tenant_id)
        return create_response(data={
            "items": [{
                "id": r.id,
                "name": r.name,
                "title": r.title,
                "jurisdiction": r.jurisdiction,
                "category": r.category,
                "status": r.status.value,
                "version": r.version,
                "effective_date": r.effective_date.isoformat() if r.effective_date else None,
            } for r in regulations],
            "total": total,
            "skip": skip,
            "limit": limit,
        })

    @router.get("/{regulation_id}")
    async def get_regulation(regulation_id: str) -> dict[str, Any]:
        try:
            regulation = await regulation_service.get_regulation(regulation_id)
            return create_response(data={
                "id": regulation.id,
                "name": regulation.name,
                "title": regulation.title,
                "jurisdiction": regulation.jurisdiction,
                "category": regulation.category,
                "description": regulation.description,
                "status": regulation.status.value,
                "version": regulation.version,
                "effective_date": regulation.effective_date.isoformat() if regulation.effective_date else None,
                "expiration_date": regulation.expiration_date.isoformat() if regulation.expiration_date else None,
                "source_url": regulation.source_url,
                "tags": regulation.tags,
                "requirements": [{
                    "id": req.id,
                    "title": req.title,
                    "category": req.category,
                    "mandatory": req.mandatory,
                } for req in regulation.requirements],
                "created_by": regulation.created_by,
                "created_at": regulation.created_at.isoformat(),
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def create_regulation(body: Regulation, created_by: str = "") -> dict[str, Any]:
        try:
            regulation = await regulation_service.create_regulation(body, created_by)
            return create_response(data={"id": regulation.id, "name": regulation.name})
        except ConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    @router.put("/{regulation_id}")
    async def update_regulation(regulation_id: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            regulation = await regulation_service.update_regulation(regulation_id, body)
            return create_response(data={"id": regulation.id, "status": regulation.status.value})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/{regulation_id}/status")
    async def change_status(regulation_id: str, status: RegulationStatus) -> dict[str, Any]:
        try:
            regulation = await regulation_service.change_status(regulation_id, status)
            return create_response(data={"id": regulation.id, "status": regulation.status.value})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/{regulation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_regulation(regulation_id: str) -> Response:
        try:
            await regulation_service.delete_regulation(regulation_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.get("/{regulation_id}/requirements")
    async def list_requirements(regulation_id: str) -> dict[str, Any]:
        requirements = await regulation_service.list_requirements(regulation_id)
        return create_response(data=[{
            "id": req.id,
            "title": req.title,
            "description": req.description,
            "category": req.category,
            "mandatory": req.mandatory,
            "deadline": req.deadline.isoformat() if req.deadline else None,
        } for req in requirements])

    @router.post("/{regulation_id}/requirements")
    async def add_requirement(regulation_id: str, body: ComplianceRequirement) -> dict[str, Any]:
        try:
            requirement = await regulation_service.add_requirement(regulation_id, body)
            return create_response(data={"id": requirement.id})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.get("/assessments")
    async def list_assessments(
        skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
    ) -> dict[str, Any]:
        assessments, total = await regulation_service.list_assessments(skip, limit)
        return create_response(data={
            "items": [{
                "id": a.id,
                "regulation_id": a.regulation_id,
                "entity_id": a.entity_id,
                "entity_type": a.entity_type,
                "status": a.status,
                "score": a.score,
                "assessed_by": a.assessed_by,
                "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
            } for a in assessments],
            "total": total,
        })

    @router.post("/assessments")
    async def create_assessment(body: Assessment) -> dict[str, Any]:
        assessment = await regulation_service.create_assessment(body)
        return create_response(data={"id": assessment.id})

    return router
