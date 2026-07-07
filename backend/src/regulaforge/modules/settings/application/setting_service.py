from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.common.exceptions import NotFoundError, ValidationError
from regulaforge.modules.settings.domain.models import Setting, SettingCategory
from regulaforge.modules.settings.domain.repository import SettingRepository

logger = logging.getLogger(__name__)


class SettingService:
    def __init__(self, setting_repo: SettingRepository) -> None:
        self._setting_repo = setting_repo

    async def get(self, key: str, tenant_id: Optional[str] = None) -> Setting:
        setting = await self._setting_repo.get(key, tenant_id)
        if not setting:
            raise NotFoundError(f"Setting '{key}' not found")
        return setting

    async def get_value(self, key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
        setting = await self._setting_repo.get(key, tenant_id)
        if not setting:
            return default
        return setting.value

    async def get_many(self, keys: list[str], tenant_id: Optional[str] = None) -> dict[str, Any]:
        settings = await self._setting_repo.get_many(keys, tenant_id)
        return {s.key: s.value for s in settings}

    async def get_by_category(self, category: SettingCategory, tenant_id: Optional[str] = None) -> list[Setting]:
        return await self._setting_repo.find_by_category(category.value, tenant_id)

    async def get_all(self, tenant_id: Optional[str] = None) -> list[Setting]:
        return await self._setting_repo.find_all(tenant_id)

    async def set(self, setting: Setting) -> Setting:
        return await self._setting_repo.set(setting)

    async def set_many(self, settings: list[Setting]) -> list[Setting]:
        return await self._setting_repo.set_many(settings)

    async def delete(self, key: str, tenant_id: Optional[str] = None) -> None:
        setting = await self._setting_repo.get(key, tenant_id)
        if not setting:
            raise NotFoundError(f"Setting '{key}' not found")
        await self._setting_repo.delete(key, tenant_id)

    async def update_setting(
        self, key: str, value: Any, updated_by: str = "", tenant_id: Optional[str] = None,
    ) -> Setting:
        setting = await self._setting_repo.get(key, tenant_id)
        if not setting:
            raise NotFoundError(f"Setting '{key}' not found")
        setting.value = value
        setting.updated_by = updated_by
        return await self._setting_repo.set(setting)
