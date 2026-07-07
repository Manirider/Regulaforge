"""Authentication and authorization middleware for FastAPI.

Provides dependency injection functions for JWT-based authentication,
role-based access control (RBAC), permission-based access control,
and tenant context extraction.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.application.ports.auth import IAuthTokenService
from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.user import User
from regulaforge.domain.repositories.user_repository import UserRepository
from regulaforge.infrastructure.persistence.adapters.user_repository_adapter import (
    SqlAlchemyUserRepository,
)
from regulaforge.infrastructure.persistence.database import get_session
from regulaforge.infrastructure.security.adapters.token_service_adapter import JwtTokenAdapter
from regulaforge.infrastructure.security.jwt_service import JWTService

logger = get_logger(__name__)

# Security scheme
bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="JWT access token (format: 'Bearer <token>')",
    auto_error=False,
)

# Singleton token service adapter
_token_service: Optional[IAuthTokenService] = None


def get_token_service() -> IAuthTokenService:
    """Get or create the IAuthTokenService singleton via adapter."""
    global _token_service
    if _token_service is None:
        _token_service = JwtTokenAdapter(JWTService())
    return _token_service


@asynccontextmanager
async def _get_read_session() -> AsyncIterator[AsyncSession]:
    """Get a read-only database session."""
    async for session in get_session():
        yield session
        break


async def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[str]:
    """Extract the Bearer token from the Authorization header."""
    if credentials is None:
        return None
    return credentials.credentials


async def get_current_user(
    token: str = Depends(get_token_from_header),
) -> User:
    """Get the current authenticated user from the JWT token."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_service = get_token_service()

    try:
        payload = token_service.verify_token(token, expected_type="access")
    except ValueError as e:
        error_msg = str(e)
        if "expired" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.warning("Invalid token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.subject
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with _get_read_session() as session:
        repository: UserRepository = SqlAlchemyUserRepository(session)
        user = await repository.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    token: str = Depends(get_token_from_header),
) -> Optional[User]:
    """Get the current user if authenticated, None otherwise."""
    if token is None:
        return None

    try:
        return await get_current_user(token=token)
    except HTTPException:
        return None


def require_permission(
    permission: str,
) -> Callable[[User], User]:
    """Create a dependency that requires a specific permission."""
    async def _require_permission(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user

        async with _get_read_session() as session:
            from regulaforge.domain.repositories.role_repository import RoleRepository
            from regulaforge.infrastructure.persistence.adapters.role_repository_adapter import (
                SqlAlchemyRoleRepository,
            )
            role_repo: RoleRepository = SqlAlchemyRoleRepository(session)
            has_permission = await role_repo.user_has_permission(
                current_user.id, permission
            )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )

        return current_user

    return _require_permission


def require_role(
    role_name: str,
) -> Callable[[User], User]:
    """Create a dependency that requires a specific role."""
    async def _require_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user

        async with _get_read_session() as session:
            from regulaforge.domain.repositories.role_repository import RoleRepository
            from regulaforge.infrastructure.persistence.adapters.role_repository_adapter import (
                SqlAlchemyRoleRepository,
            )
            role_repo: RoleRepository = SqlAlchemyRoleRepository(session)
            has_role = await role_repo.user_has_role(
                current_user.id, role_name
            )

        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role not assigned: {role_name}",
            )

        return current_user

    return _require_role


async def get_current_tenant(
    current_user: User = Depends(get_current_user),
) -> Optional[dict[str, Any]]:
    """Get the current tenant context from the authenticated user."""
    if current_user.tenant_id is None:
        return None

    async with _get_read_session() as session:
        from sqlalchemy import select

        from regulaforge.infrastructure.persistence.models.tenant_model import TenantModel

        result = await session.execute(
            select(TenantModel).where(TenantModel.id == current_user.tenant_id)
        )
        tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is deactivated",
        )

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "domain": tenant.domain,
        "settings": tenant.settings,
    }
