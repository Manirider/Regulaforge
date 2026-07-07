from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response

from regulaforge.common.exceptions import NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.contracts.application.contract_service import ContractService
from regulaforge.modules.contracts.domain.models import Clause, Contract, ContractStatus, Template

logger = logging.getLogger(__name__)


def create_contracts_router(
    contract_service: Optional[ContractService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/contracts",
        tags=["Contracts"],
        dependencies=dependencies or [],
    )

    @router.get("")
    async def list_contracts(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        contracts, total = await contract_service.list_contracts(skip, limit, tenant_id)
        return create_response(data={
            "items": [{
                "id": c.id,
                "title": c.title,
                "status": c.status.value,
                "contract_type": c.contract_type,
                "current_version": c.current_version,
                "parties": len(c.parties),
                "effective_date": c.effective_date.isoformat() if c.effective_date else None,
                "expiration_date": c.expiration_date.isoformat() if c.expiration_date else None,
                "created_by": c.created_by,
                "created_at": c.created_at.isoformat(),
            } for c in contracts],
            "total": total,
            "skip": skip,
            "limit": limit,
        })

    @router.get("/{contract_id}")
    async def get_contract(contract_id: str) -> dict[str, Any]:
        try:
            contract = await contract_service.get_contract(contract_id)
            return create_response(data={
                "id": contract.id,
                "title": contract.title,
                "description": contract.description,
                "status": contract.status.value,
                "contract_type": contract.contract_type,
                "content": contract.content,
                "clauses": [{
                    "id": cl.id,
                    "title": cl.title,
                    "type": cl.type,
                    "category": cl.category,
                    "is_negotiable": cl.is_negotiable,
                } for cl in contract.clauses],
                "parties": contract.parties,
                "effective_date": contract.effective_date.isoformat() if contract.effective_date else None,
                "expiration_date": contract.expiration_date.isoformat() if contract.expiration_date else None,
                "signed_date": contract.signed_date.isoformat() if contract.signed_date else None,
                "current_version": contract.current_version,
                "tags": contract.tags,
                "metadata": contract.metadata,
                "created_by": contract.created_by,
                "created_at": contract.created_at.isoformat(),
                "updated_at": contract.updated_at.isoformat(),
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def create_contract(body: Contract, created_by: str = "") -> dict[str, Any]:
        contract = await contract_service.create_contract(body, created_by)
        return create_response(data={"id": contract.id, "status": contract.status.value})

    @router.put("/{contract_id}")
    async def update_contract(contract_id: str, body: dict[str, Any], updated_by: str = "") -> dict[str, Any]:
        try:
            contract = await contract_service.update_contract(contract_id, body, updated_by)
            return create_response(data={"id": contract.id, "version": contract.current_version})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/{contract_id}/status")
    async def change_status(contract_id: str, status: ContractStatus, changed_by: str = "") -> dict[str, Any]:
        try:
            contract = await contract_service.change_status(contract_id, status, changed_by)
            return create_response(data={"id": contract.id, "status": contract.status.value})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_contract(contract_id: str) -> Response:
        try:
            await contract_service.delete_contract(contract_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.get("/{contract_id}/versions")
    async def list_versions(contract_id: str) -> dict[str, Any]:
        versions = await contract_service.list_versions(contract_id)
        return create_response(data=[{
            "id": v.id,
            "version_number": v.version_number,
            "changes_summary": v.changes_summary,
            "created_by": v.created_by,
            "created_at": v.created_at.isoformat(),
        } for v in versions])

    @router.get("/templates")
    async def list_templates(
        skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
    ) -> dict[str, Any]:
        templates, total = await contract_service.list_templates(skip, limit)
        return create_response(data={
            "items": [{
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "version": t.version,
                "is_published": t.is_published,
            } for t in templates],
            "total": total,
        })

    @router.post("/templates", status_code=status.HTTP_201_CREATED)
    async def create_template(body: Template) -> dict[str, Any]:
        template = await contract_service.create_template(body)
        return create_response(data={"id": template.id, "name": template.name})

    @router.put("/templates/{template_id}")
    async def update_template(template_id: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            template = await contract_service.update_template(template_id, body)
            return create_response(data={"id": template.id})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_template(template_id: str) -> Response:
        try:
            await contract_service.delete_template(template_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/clauses")
    async def create_clause(body: Clause) -> dict[str, Any]:
        clause = await contract_service.create_clause(body)
        return create_response(data={"id": clause.id, "title": clause.title})

    @router.get("/clauses")
    async def list_clauses(category: Optional[str] = None) -> dict[str, Any]:
        clauses = await contract_service.list_clauses(category)
        return create_response(data=[{
            "id": c.id,
            "title": c.title,
            "type": c.type,
            "category": c.category,
            "version": c.version,
            "is_negotiable": c.is_negotiable,
        } for c in clauses])

    return router
