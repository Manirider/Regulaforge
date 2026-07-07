from __future__ import annotations

from typing import Optional

from regulaforge.modules.users.domain.models import User


class UserRepository:
    async def find_by_id(self, user_id: str) -> Optional[User]:
        raise NotImplementedError

    async def find_by_email(self, email: str) -> Optional[User]:
        raise NotImplementedError

    async def find_by_username(self, username: str) -> Optional[User]:
        raise NotImplementedError

    async def find_all(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> list[User]:
        raise NotImplementedError

    async def count(self, tenant_id: Optional[str] = None) -> int:
        raise NotImplementedError

    async def save(self, user: User) -> User:
        raise NotImplementedError

    async def delete(self, user_id: str) -> None:
        raise NotImplementedError
