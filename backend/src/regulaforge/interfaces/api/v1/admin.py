from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from regulaforge.config.logging import get_logger
from regulaforge.domain.repositories.base import EntityNotFoundError
from regulaforge.interfaces.api.dependencies import (
    get_role_repo,
    get_user_repo,
)
from regulaforge.interfaces.api.middleware.auth_middleware import (
    get_current_user,
    require_role,
)
from regulaforge.interfaces.api.v1.schemas import (
    MessageResponse,
    PaginatedResponse,
    RoleResponse,
    UserResponse,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get(
    "/users",
    summary="List all users (admin)",
    responses={200: {"description": "Paginated list of users"}},
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    email: str = Query(None),
    is_active: bool = Query(None),
    user_repo=Depends(get_user_repo),  # noqa: B008
) -> PaginatedResponse:
    filters: dict[str, Any] = {}
    if email:
        filters["email"] = email
    if is_active is not None:
        filters["is_active"] = is_active
    users, total = await user_repo.search(filters=filters, page=page, page_size=page_size)
    return PaginatedResponse(
        items=[UserResponse.from_domain(u).model_dump() for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get(
    "/users/{user_id}",
    summary="Get user by ID (admin)",
    responses={200: {"description": "User details"}, 404: {"description": "User not found"}},
)
async def get_user(
    user_id: UUID,
    user_repo=Depends(get_user_repo),  # noqa: B008
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.from_domain(user)


@router.patch(
    "/users/{user_id}",
    summary="Update user (admin)",
    responses={200: {"description": "User updated"}, 404: {"description": "User not found"}},
)
async def update_user(
    user_id: UUID,
    updates: dict[str, Any],
    _current_user=Depends(get_current_user),  # noqa: B008
    user_repo=Depends(get_user_repo),  # noqa: B008
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    allowed_fields = {"full_name", "is_active"}
    for field, value in updates.items():
        if field not in allowed_fields:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot update field: {field}",
            )
        if field == "is_active":
            if value:
                user.activate()
            else:
                user.deactivate()
        elif field == "full_name":
            object.__setattr__(user, "_full_name", value)
    saved = await user_repo.save(user)
    return UserResponse.from_domain(saved)


@router.post(
    "/users/{user_id}/deactivate",
    summary="Deactivate a user (admin)",
    responses={200: {"description": "User deactivated"}, 404: {"description": "User not found"}},
)
async def deactivate_user(
    user_id: UUID,
    user_repo=Depends(get_user_repo),  # noqa: B008
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.deactivate()
    saved = await user_repo.save(user)
    return UserResponse.from_domain(saved)


@router.post(
    "/users/{user_id}/activate",
    summary="Activate a user (admin)",
    responses={200: {"description": "User activated"}, 404: {"description": "User not found"}},
)
async def activate_user(
    user_id: UUID,
    user_repo=Depends(get_user_repo),  # noqa: B008
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.activate()
    saved = await user_repo.save(user)
    return UserResponse.from_domain(saved)


@router.get(
    "/roles",
    summary="List all roles (admin)",
    responses={200: {"description": "List of roles"}},
)
async def list_roles(
    role_repo=Depends(get_role_repo),  # noqa: B008
) -> list[RoleResponse]:
    roles, _ = await role_repo.search(filters={}, page=1, page_size=100)
    return [RoleResponse.from_domain(r) for r in roles]


@router.post(
    "/roles",
    summary="Create a new role (admin)",
    status_code=status.HTTP_201_CREATED,
    responses={201: {"description": "Role created"}, 400: {"description": "Validation error"}},
)
async def create_role(
    name: str,
    description: str | None = None,
    permissions: list[str] | None = None,
    role_repo=Depends(get_role_repo),  # noqa: B008
) -> RoleResponse:
    from regulaforge.domain.entities.role import Role
    if permissions is None:
        permissions = []
    existing = await role_repo.get_by_name(name)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")
    role = Role.create(name=name, description=description)
    if permissions:
        role.set_permissions(permissions)
    saved = await role_repo.save(role)
    return RoleResponse.from_domain(saved)


@router.post(
    "/users/{user_id}/roles/{role_id}",
    summary="Assign a role to a user (admin)",
    responses={200: {"description": "Role assigned"}, 404: {"description": "User or role not found"}},
)
async def assign_role(
    user_id: UUID,
    role_id: UUID,
    role_repo=Depends(get_role_repo),  # noqa: B008
) -> MessageResponse:
    try:
        await role_repo.assign_role_to_user(user_id, role_id)
        return MessageResponse(message="Role assigned successfully")
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    summary="Remove a role from a user (admin)",
    responses={200: {"description": "Role removed"}, 404: {"description": "User or role not found"}},
)
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    role_repo=Depends(get_role_repo),  # noqa: B008
) -> MessageResponse:
    try:
        await role_repo.remove_role_from_user(user_id, role_id)
        return MessageResponse(message="Role removed successfully")
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
