from __future__ import annotations

from typing import Any, Optional

from regulaforge.modules.settings.domain.models import Setting


class SettingRepository:
    async def get(self, key: str, tenant_id: Optional[str] = None) -> Optional[Setting]:
        raise NotImplementedError

    async def get_many(self, keys: list[str], tenant_id: Optional[str] = None) -> list[Setting]:
        raise NotImplementedError

    async def find_by_category(self, category: str, tenant_id: Optional[str] = None) -> list[Setting]:
        raise NotImplementedError

    async def find_all(self, tenant_id: Optional[str] = None) -> list[Setting]:
        raise NotImplementedError

    async def set(self, setting: Setting) -> Setting:
        raise NotImplementedError

    async def set_many(self, settings: list[Setting]) -> list[Setting]:
        raise NotImplementedError

    async def delete(self, key: str, tenant_id: Optional[str] = None) -> None:
        raise NotImplementedError
