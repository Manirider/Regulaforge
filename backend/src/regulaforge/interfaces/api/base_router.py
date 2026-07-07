"""Base API router and standardized response schemas."""

from typing import Any, Generic, Optional, TypeVar

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standardized top-level API response envelope."""

    status: str = Field(default="success", description="Response status (success or error)")
    data: Optional[T] = Field(default=None, description="Response payload")
    message: Optional[str] = Field(default=None, description="Optional developer/user message")
    meta: dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")


class PaginationMetadata(BaseModel):
    """Metadata about a paginated result set."""

    total: int = Field(..., description="Total number of items matching filters")
    page: int = Field(..., description="Current page number (1-indexed)")
    pages: int = Field(..., description="Total pages based on page size")
    page_size: int = Field(..., description="Items per page")


class PaginatedResponse(ApiResponse[list[T]]):
    """Standardized response envelope for list endpoints."""

    meta: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class ErrorDetails(BaseModel):
    """Structure of an API error payload."""

    code: str = Field(..., description="Classification error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Any] = Field(default=None, description="Optional context-specific error details")


class ErrorResponse(BaseModel):
    """Standardized error response wrapper."""

    status: str = Field(default="error")
    error: ErrorDetails


def create_versioned_router(
    prefix: str,
    tags: list[str],
    **kwargs: Any,
) -> APIRouter:
    """Create a configured FastAPI router with default options.

    Args:
        prefix: URL path prefix.
        tags: OpenAPI document tags.
        kwargs: Additional arguments passed to APIRouter.

    Returns:
        A configured APIRouter instance.
    """
    return APIRouter(prefix=prefix, tags=tags, **kwargs)


def pagination_params(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> dict[str, int]:
    """FastAPI dependency for extracting pagination parameters.

    Returns:
        A dictionary containing 'page' and 'page_size'.
    """
    return {"page": page, "page_size": page_size}


async def current_user() -> dict[str, Any]:
    """FastAPI dependency placeholder for extracting the authenticated user.

    Returns:
        A dictionary representing the current active user context.
    """
    return {
        "id": "00000000-0000-0000-0000-000000000000",
        "username": "system_admin",
        "role": "admin",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
    }
