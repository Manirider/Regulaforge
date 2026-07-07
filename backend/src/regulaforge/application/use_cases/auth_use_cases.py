from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from regulaforge.application.ports.auth import IAuthTokenService, IPasswordService, TokenPayload
from regulaforge.config.constants import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PASSWORD_REQUIRE_DIGIT,
    PASSWORD_REQUIRE_LOWERCASE,
    PASSWORD_REQUIRE_SPECIAL,
    PASSWORD_REQUIRE_UPPERCASE,
)
from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.user import User
from regulaforge.domain.repositories.role_repository import RoleRepository
from regulaforge.domain.repositories.user_repository import UserRepository

logger = get_logger(__name__)


def validate_password(password: str) -> None:
    """Validate password meets configured policy requirements.

    Args:
        password: The plain-text password to validate.

    Raises:
        ValueError: If any policy requirement is not met.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must not exceed {MAX_PASSWORD_LENGTH} characters")
    if PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    if PASSWORD_REQUIRE_SPECIAL and not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in password):
        raise ValueError("Password must contain at least one special character")


class RegisterUserUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        role_repo: RoleRepository,
        password_service: IPasswordService,
    ) -> None:
        self._user_repo = user_repo
        self._role_repo = role_repo
        self._password_service = password_service

    async def execute(
        self,
        email: str,
        username: str,
        password: str,
        full_name: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
    ) -> User:
        existing = await self._user_repo.get_by_email(email)
        if existing is not None:
            raise ValueError("A user with this email already exists")

        existing_username = await self._user_repo.search({"username": username}, page=1, page_size=1)
        if existing_username[1] > 0:
            raise ValueError("A user with this username already exists")

        validate_password(password)
        password_hash = self._password_service.hash_password(password)

        user = User(
            email=email,
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            tenant_id=tenant_id,
        )

        saved = await self._user_repo.save(user)
        logger.info("User registered: %s (%s)", email, username)
        return saved


class LoginUserUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        password_service: IPasswordService,
        jwt_service: IAuthTokenService,
    ) -> None:
        self._user_repo = user_repo
        self._password_service = password_service
        self._jwt_service = jwt_service

    async def execute(
        self,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        user = await self._user_repo.get_by_email(email)
        if user is None:
            raise ValueError("Invalid email or password")

        if user.is_locked:
            raise ValueError("Account is temporarily locked due to too many failed attempts")

        if not self._password_service.verify_password(password, user.password_hash):
            user.record_failed_attempt()
            await self._user_repo.save(user)
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated. Contact your administrator.")

        user.record_login()
        await self._user_repo.save(user)

        access_token = self._jwt_service.create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id) if user.tenant_id else None,
        )
        refresh_token = self._jwt_service.create_refresh_token(
            subject=str(user.id),
        )

        logger.info("User logged in: %s", email)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user.to_dict(),
        }


class RefreshTokenUseCase:
    def __init__(self, jwt_service: IAuthTokenService, user_repo: UserRepository) -> None:
        self._jwt_service = jwt_service
        self._user_repo = user_repo

    async def execute(self, refresh_token: str) -> dict[str, str]:
        payload: TokenPayload = self._jwt_service.verify_token(refresh_token, expected_type="refresh")
        if not payload.subject:
            raise ValueError("Invalid refresh token: missing subject")

        user = await self._user_repo.get_by_id(UUID(payload.subject))
        if user is None:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("Account is deactivated")

        access_token = self._jwt_service.create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id) if user.tenant_id else None,
        )
        return {"access_token": access_token, "token_type": "bearer"}


class ChangePasswordUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        password_service: IPasswordService,
    ) -> None:
        self._user_repo = user_repo
        self._password_service = password_service

    async def execute(
        self,
        user: User,
        old_password: str,
        new_password: str,
    ) -> None:
        if not self._password_service.verify_password(old_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        validate_password(new_password)
        new_hash = self._password_service.hash_password(new_password)
        user.set_password_hash(new_hash)
        await self._user_repo.save(user)
        logger.info("Password changed for user: %s", user.email)
