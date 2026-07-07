from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from regulaforge.common.exceptions import (
    AuthenticationError,
    ConflictError,
    ValidationError,
)
from regulaforge.config.settings import settings
from regulaforge.infrastructure.security.jwt_service import JWTService
from regulaforge.infrastructure.security.password_service import PasswordService
from regulaforge.modules.auth.domain.events import (
    LoginFailed,
    TokenRefreshed,
    UserLoggedIn,
    UserLoggedOut,
    UserRegistered,
)
from regulaforge.modules.auth.domain.models import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    TokenType,
)
from regulaforge.modules.users.domain.models import User, UserProfile, UserStatus
from regulaforge.modules.users.domain.repository import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        jwt_service: JWTService,
        password_service: PasswordService,
    ) -> None:
        self._user_repo = user_repository
        self._jwt = jwt_service
        self._password = password_service

    async def register(self, request: RegisterRequest) -> LoginResponse:
        existing = await self._user_repo.find_by_email(request.email)
        if existing:
            raise ConflictError(f"User with email {request.email} already exists")

        if not self._password.validate_password_strength(request.password):
            raise ValidationError(
                "Password must be at least 8 characters with uppercase, lowercase, digit, and special character"
            )

        hashed = self._password.hash_password(request.password)
        user = User(
            email=request.email,
            hashed_password=hashed,
            profile=UserProfile(full_name=request.full_name) if hasattr(request, "full_name") else UserProfile(),
            tenant_id=request.tenant_id or "",
            status=UserStatus.ACTIVE,
        )
        created = await self._user_repo.save(user)

        logger.info("User registered: %s (%s)", created.id, created.email)
        return await self._create_login_response(created)

    async def login(self, request: LoginRequest) -> LoginResponse:
        user = await self._user_repo.find_by_email(request.email)
        if not user:
            logger.warning("Login failed: unknown email %s", request.email)
            raise AuthenticationError("Invalid email or password")

        if user.status != UserStatus.ACTIVE:
            logger.warning("Login failed: user %s status=%s", user.id, user.status.value)
            raise AuthenticationError("Account is not active")

        if not self._password.verify_password(request.password, user.hashed_password):
            logger.warning("Login failed: wrong password for %s", request.email)
            raise AuthenticationError("Invalid email or password")

        user.last_login_at = datetime.utcnow()
        await self._user_repo.save(user)

        logger.info("User logged in: %s", user.email)
        return await self._create_login_response(user, request.remember_me)

    async def refresh_token(self, refresh_token: str) -> LoginResponse:
        payload = self._jwt.decode_refresh_token(refresh_token)
        if not payload:
            raise AuthenticationError("Invalid or expired refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token payload")

        user = await self._user_repo.find_by_id(user_id)
        if not user or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("User not found or inactive")

        logger.info("Token refreshed for user: %s", user.email)
        return await self._create_login_response(user)

    async def logout(self, user_id: str, token_jti: str) -> None:
        self._jwt.revoke_token(token_jti)
        logger.info("User logged out: %s", user_id)

    async def _create_login_response(
        self,
        user: User,
        remember_me: bool = False,
    ) -> LoginResponse:
        access_ttl = timedelta(days=7) if remember_me else timedelta(hours=1)
        refresh_ttl = timedelta(days=30) if remember_me else timedelta(days=7)

        access_token, access_jti = self._jwt.create_access_token(
            user_id=user.id,
            email=user.email,
            roles=[],
            permissions=[],
            expires_delta=access_ttl,
        )
        refresh_token, refresh_jti = self._jwt.create_refresh_token(
            user_id=user.id,
            expires_delta=refresh_ttl,
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(access_ttl.total_seconds()),
            user_id=user.id,
            email=user.email,
            roles=[],
            permissions=[],
        )
