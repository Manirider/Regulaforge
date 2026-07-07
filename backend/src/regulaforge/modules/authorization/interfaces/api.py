from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from regulaforge.common.exceptions import ForbiddenError, NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.authorization.application.authorization_service import AuthorizationService
from regulaforge.modules.authorization.domain.models import Action, Permission, Resource, Role

logger = logging.getLogger(__name__)


def create_authorization_router(
    authz_service: Optional[AuthorizationService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(prefix="/authorization", tags=["Authorization"], dependencies=dependencies or [])

    @router.get("/roles")
    async def list_roles() -> dict[str, Any]:
        roles = await authz_service._role_repo.find_all()
        return create_response(data=[{
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "permissions": len(r.permissions),
            "is_system": r.is_system,
        } for r in roles])

    @router.post("/roles", status_code=status.HTTP_201_CREATED)
    async def create_role(body: Role) -> dict[str, Any]:
        created = await authz_service.create_role(body)
        return create_response(data={"id": created.id, "name": created.name})

    @router.put("/roles/{role_id}")
    async def update_role(role_id: str, body: Role) -> dict[str, Any]:
        body.id = role_id
        try:
            updated = await authz_service.update_role(body)
            return create_response(data={"id": updated.id, "name": updated.name})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/roles/{role_id}")
    async def delete_role(role_id: str) -> dict[str, Any]:
        try:
            await authz_service.delete_role(role_id)
            return create_response(message="Role deleted")
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/roles/assign")
    async def assign_role(
        user_id: str, role_id: str, assigned_by: str, tenant_id: str = "",
    ) -> dict[str, Any]:
        try:
            assignment = await authz_service.assign_role(user_id, role_id, assigned_by, tenant_id)
            return create_response(data={"assignment_id": assignment.id})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.get("/permissions/{user_id}")
    async def get_user_permissions(user_id: str) -> dict[str, Any]:
        permissions = await authz_service.get_user_permissions(user_id)
        return create_response(data=[{
            "resource": p.resource.value,
            "action": p.action.value,
            "conditions": p.conditions,
        } for p in permissions])

    return router
