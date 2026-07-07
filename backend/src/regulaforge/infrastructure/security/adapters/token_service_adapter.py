"""Adapter: JWT-based IAuthTokenService implementation.

Wraps the existing JWTService behind the IAuthTokenService port,
allowing the application layer to depend on the abstraction
rather than the concrete JWT implementation.
"""

from typing import Any, Optional

import jwt
from regulaforge.application.ports.auth import IAuthTokenService, IPasswordService, TokenPayload
from regulaforge.infrastructure.security.jwt_service import JWTService
from regulaforge.infrastructure.security.password_service import PasswordService


class JwtTokenAdapter(IAuthTokenService):
    """IAuthTokenService adapter backed by JWTService.

    Translates between the port interface (TokenPayload) and
    the raw dict payload returned by the JWT library.
    """

    def __init__(self, jwt_service: JWTService) -> None:
        self._jwt_service = jwt_service

    def create_access_token(
        self,
        subject: str,
        tenant_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        return self._jwt_service.create_access_token(
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
            additional_claims=additional_claims,
        )

    def create_refresh_token(
        self,
        subject: str,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        return self._jwt_service.create_refresh_token(
            subject=subject,
            additional_claims=additional_claims,
        )

    def verify_token(
        self, token: str, expected_type: Optional[str] = None
    ) -> TokenPayload:
        try:
            raw = self._jwt_service.verify_token(token, expected_type=expected_type)
            return self._raw_to_payload(raw)
        except jwt.PyJWTError as e:
            raise ValueError(str(e)) from e

    def decode_token(self, token: str, verify: bool = True) -> TokenPayload:
        try:
            raw = self._jwt_service.decode_token(token, verify=verify)
            return self._raw_to_payload(raw)
        except jwt.PyJWTError as e:
            raise ValueError(str(e)) from e

    def get_subject(self, token: str) -> str:
        return self._jwt_service.get_subject(token)

    def is_token_expired(self, token: str) -> bool:
        return self._jwt_service.is_token_expired(token)

    @staticmethod
    def _raw_to_payload(raw: dict[str, Any]) -> TokenPayload:
        return TokenPayload(
            subject=raw.get("sub", ""),
            token_type=raw.get("token_type", "access"),
            tenant_id=raw.get("tenant_id"),
            roles=raw.get("roles"),
            extra={k: v for k, v in raw.items()
                    if k not in ("sub", "token_type", "tenant_id", "roles", "exp", "iat", "jti")},
        )


class PasswordServiceAdapter(IPasswordService):
    """IPasswordService adapter backed by PasswordService."""

    def __init__(self, password_service: PasswordService) -> None:
        self._password_service = password_service

    def hash_password(self, password: str) -> str:
        return self._password_service.hash_password(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return self._password_service.verify_password(password, password_hash)

    def is_hash_stale(self, password_hash: str) -> bool:
        return self._password_service.is_hash_stale(password_hash)
