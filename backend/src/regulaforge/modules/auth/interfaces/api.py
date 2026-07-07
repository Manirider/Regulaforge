from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from regulaforge.common.exceptions import AuthenticationError, ConflictError, ValidationError
from regulaforge.common.utils import create_response
from regulaforge.modules.auth.application.auth_service import AuthService
from regulaforge.modules.auth.domain.models import LoginRequest, RegisterRequest

logger = logging.getLogger(__name__)


def create_auth_router(
    auth_service: Optional[AuthService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Authentication"], dependencies=dependencies or [])

    @router.post("/register", status_code=status.HTTP_201_CREATED)
    async def register(body: RegisterRequest) -> dict[str, Any]:
        try:
            result = await auth_service.register(body)
            return create_response(data={
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": result.token_type,
                "expires_in": result.expires_in,
                "user_id": result.user_id,
            })
        except ConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    @router.post("/login")
    async def login(body: LoginRequest) -> dict[str, Any]:
        try:
            result = await auth_service.login(body)
            return create_response(data={
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": result.token_type,
                "expires_in": result.expires_in,
                "user_id": result.user_id,
                "email": result.email,
                "roles": result.roles,
                "permissions": result.permissions,
            })
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    @router.post("/refresh")
    async def refresh(body: dict[str, str]) -> dict[str, Any]:
        token = body.get("refresh_token", "")
        if not token:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="refresh_token is required")
        try:
            result = await auth_service.refresh_token(token)
            return create_response(data={
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": result.token_type,
                "expires_in": result.expires_in,
            })
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    @router.post("/logout")
    async def logout(user_id: str = "", token_jti: str = "") -> dict[str, Any]:
        try:
            await auth_service.logout(user_id, token_jti)
            return create_response(message="Logged out successfully")
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return router
