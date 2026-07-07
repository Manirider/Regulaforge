from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response

from regulaforge.common.exceptions import ConflictError, NotFoundError, ValidationError
from regulaforge.common.utils import create_response
from regulaforge.modules.users.application.user_service import UserService
from regulaforge.modules.users.domain.models import UserProfile

logger = logging.getLogger(__name__)


def create_users_router(
    user_service: Optional[UserService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/users",
        tags=["Users"],
        dependencies=dependencies or [],
    )

    @router.get("")
    async def list_users(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        users, total = await user_service.list_users(skip, limit, tenant_id)
        return create_response(data={
            "items": [{
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "status": u.status.value,
                "tenant_id": u.tenant_id,
                "created_at": u.created_at.isoformat(),
            } for u in users],
            "total": total,
            "skip": skip,
            "limit": limit,
        })

    @router.get("/{user_id}")
    async def get_user(user_id: str) -> dict[str, Any]:
        try:
            user = await user_service.get_user(user_id)
            return create_response(data={
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "status": user.status.value,
                "profile": {
                    "first_name": user.profile.first_name,
                    "last_name": user.profile.last_name,
                    "phone": user.profile.phone,
                    "department": user.profile.department,
                    "title": user.profile.title,
                },
                "tenant_id": user.tenant_id,
                "mfa_enabled": user.mfa_enabled,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "created_at": user.created_at.isoformat(),
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.put("/{user_id}")
    async def update_user(user_id: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            user = await user_service.update_user(user_id, body)
            return create_response(data={"id": user.id, "status": user.status.value})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.put("/{user_id}/profile")
    async def update_profile(user_id: str, profile: UserProfile) -> dict[str, Any]:
        try:
            user = await user_service.update_profile(user_id, profile)
            return create_response(data={"id": user.id})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/{user_id}/deactivate")
    async def deactivate_user(user_id: str) -> dict[str, Any]:
        try:
            await user_service.deactivate_user(user_id)
            return create_response(message="User deactivated")
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/{user_id}/activate")
    async def activate_user(user_id: str) -> dict[str, Any]:
        try:
            await user_service.activate_user(user_id)
            return create_response(message="User activated")
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_user(user_id: str) -> Response:
        try:
            await user_service.delete_user(user_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return router
