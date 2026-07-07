from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from regulaforge.common.exceptions import ConflictError, NotFoundError, ValidationError
from regulaforge.modules.users.domain.models import User, UserProfile, UserStatus
from regulaforge.modules.users.domain.repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, user_repo: UserRepository, password_service: Any) -> None:  # noqa: ANN401
        self._user_repo = user_repo
        self._password_service = password_service

    async def get_user(self, user_id: str) -> User:
        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def get_user_by_email(self, email: str) -> User:
        user = await self._user_repo.find_by_email(email)
        if not user:
            raise NotFoundError(f"User with email {email} not found")
        return user

    async def list_users(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> tuple[list[User], int]:
        users = await self._user_repo.find_all(skip, limit, tenant_id)
        total = await self._user_repo.count(tenant_id)
        return users, total

    async def create_user(
        self,
        email: str,
        password: str,
        username: str = "",
        profile: Optional[UserProfile] = None,
        tenant_id: str = "",
    ) -> User:
        existing = await self._user_repo.find_by_email(email)
        if existing:
            raise ConflictError(f"User with email {email} already exists")
        if username:
            existing_username = await self._user_repo.find_by_username(username)
            if existing_username:
                raise ConflictError(f"Username {username} already taken")

        hashed = self._password_service.hash_password(password)
        user = User(
            email=email,
            username=username or email.split("@")[0],
            hashed_password=hashed,
            profile=profile or UserProfile(),
            tenant_id=tenant_id,
        )
        return await self._user_repo.save(user)

    async def update_user(self, user_id: str, updates: dict) -> User:
        user = await self.get_user(user_id)
        for key, value in updates.items():
            if hasattr(user, key) and key not in ("id", "hashed_password", "created_at"):
                setattr(user, key, value)
        user.updated_at = datetime.utcnow()
        return await self._user_repo.save(user)

    async def update_profile(self, user_id: str, profile: UserProfile) -> User:
        user = await self.get_user(user_id)
        user.profile = profile
        user.updated_at = datetime.utcnow()
        return await self._user_repo.save(user)

    async def deactivate_user(self, user_id: str) -> User:
        user = await self.get_user(user_id)
        user.status = UserStatus.INACTIVE
        user.updated_at = datetime.utcnow()
        return await self._user_repo.save(user)

    async def activate_user(self, user_id: str) -> User:
        user = await self.get_user(user_id)
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.utcnow()
        return await self._user_repo.save(user)

    async def delete_user(self, user_id: str) -> None:
        user = await self.get_user(user_id)
        await self._user_repo.delete(user_id)

    async def change_password(self, user_id: str, old_password: str, new_password: str) -> User:
        user = await self.get_user(user_id)
        if not self._password_service.verify_password(old_password, user.hashed_password):
            raise ValidationError("Current password is incorrect")
        user.hashed_password = self._password_service.hash_password(new_password)
        user.updated_at = datetime.utcnow()
        return await self._user_repo.save(user)
