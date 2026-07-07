from __future__ import annotations

from typing import Optional

from regulaforge.modules.auth.domain.models import AuthToken


class AuthTokenRepository:
    async def save(self, token: AuthToken) -> AuthToken:
        raise NotImplementedError

    async def find_by_jti(self, jti: str) -> Optional[AuthToken]:
        raise NotImplementedError

    async def revoke(self, jti: str) -> None:
        raise NotImplementedError

    async def revoke_all_for_user(self, user_id: str) -> None:
        raise NotImplementedError
