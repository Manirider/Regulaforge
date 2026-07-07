from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response

from regulaforge.common.exceptions import NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.settings.application.setting_service import SettingService
from regulaforge.modules.settings.domain.models import Setting, SettingCategory

logger = logging.getLogger(__name__)


def create_settings_router(
    setting_service: Optional[SettingService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/settings",
        tags=["Settings"],
        dependencies=dependencies or [],
    )

    @router.get("")
    async def get_all_settings(tenant_id: Optional[str] = None) -> dict[str, Any]:
        settings = await setting_service.get_all(tenant_id)
        return create_response(data=[{
            "key": s.key,
            "value": s.value,
            "category": s.category.value,
            "description": s.description,
            "value_type": s.value_type,
            "is_sensitive": s.is_sensitive,
        } for s in settings])

    @router.get("/categories")
    async def get_categories() -> dict[str, Any]:
        return create_response(data=[c.value for c in SettingCategory])

    @router.get("/{key}")
    async def get_setting(key: str, tenant_id: Optional[str] = None) -> dict[str, Any]:
        try:
            setting = await setting_service.get(key, tenant_id)
            return create_response(data={
                "key": setting.key,
                "value": setting.value,
                "category": setting.category.value,
                "description": setting.description,
                "value_type": setting.value_type,
                "is_sensitive": setting.is_sensitive,
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.put("/{key}")
    async def update_setting(
        key: str,
        body: dict[str, Any],
        updated_by: str = "",
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        try:
            setting = await setting_service.update_setting(key, body.get("value"), updated_by, tenant_id)
            return create_response(data={"key": setting.key, "value": setting.value})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def create_setting(body: Setting) -> dict[str, Any]:
        setting = await setting_service.set(body)
        return create_response(data={"key": setting.key})

    @router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_setting(key: str, tenant_id: Optional[str] = None) -> Response:
        try:
            await setting_service.delete(key, tenant_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return router
