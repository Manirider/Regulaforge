"""Authentication-related dependencies (user identity extraction)."""

from uuid import UUID

from fastapi import Depends

from regulaforge.domain.entities.user import User
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user


async def get_current_user_id(
    current_user: User = Depends(get_current_user),
) -> UUID:
    """Extract the current user's UUID from the authenticated request."""
    return current_user.id
