from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from regulaforge.config.logging import get_logger
from regulaforge.interfaces.api.dependencies import (
    get_change_password_uc,
    get_login_uc,
    get_refresh_uc,
    get_register_uc,
)
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user
from regulaforge.interfaces.api.v1.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Validation error or duplicate user"},
    },
)
async def register(
    request: RegisterRequest,
    use_case=Depends(get_register_uc),  # noqa: B008
) -> UserResponse:
    try:
        user = await use_case.execute(
            email=request.email,
            username=request.username,
            password=request.password,
            full_name=request.full_name,
            tenant_id=request.tenant_id,
        )
        return UserResponse.from_domain(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/login",
    summary="Authenticate and receive JWT tokens",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        423: {"description": "Account locked"},
    },
)
async def login(
    request: LoginRequest,
    use_case=Depends(get_login_uc),  # noqa: B008
) -> TokenResponse:
    try:
        result = await use_case.execute(email=request.email, password=request.password)
        return TokenResponse(**result)
    except ValueError as e:
        msg = str(e)
        if "locked" in msg.lower():
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=msg)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)


@router.post(
    "/refresh",
    summary="Refresh access token using refresh token",
    responses={
        200: {"description": "Token refreshed"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh(
    request: RefreshTokenRequest,
    use_case=Depends(get_refresh_uc),  # noqa: B008
) -> dict[str, str]:
    try:
        return await use_case.execute(request.refresh_token)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get(
    "/me",
    summary="Get current authenticated user profile",
    responses={
        200: {"description": "Current user profile"},
        401: {"description": "Not authenticated"},
    },
)
async def get_me(
    current_user=Depends(get_current_user),  # noqa: B008
) -> UserResponse:
    return UserResponse.from_domain(current_user)


@router.post(
    "/change-password",
    summary="Change current user password",
    responses={
        200: {"description": "Password changed successfully"},
        400: {"description": "Invalid current password or new password validation failed"},
        401: {"description": "Not authenticated"},
    },
)
async def change_password(
    request: ChangePasswordRequest,
    current_user=Depends(get_current_user),  # noqa: B008
    use_case=Depends(get_change_password_uc),  # noqa: B008
) -> dict[str, str]:
    try:
        await use_case.execute(
            user=current_user,
            old_password=request.old_password,
            new_password=request.new_password,
        )
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
