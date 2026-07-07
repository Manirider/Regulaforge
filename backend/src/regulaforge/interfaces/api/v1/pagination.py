"""Pagination utilities for API endpoints.

Standardizes paginated responses across all list endpoints,
eliminating duplicated ceiling-division and response-building logic.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from regulaforge.config.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response wrapper.

    Usage:
        return Page(items=[...], total=42, page=1, page_size=20)
    """

    items: list[T]
    total: int
    page: int = DEFAULT_PAGE
    page_size: int = DEFAULT_PAGE_SIZE
    total_pages: int = 0

    def model_post_init(self, __context: Any) -> None:
        self.total_pages = max(1, (self.total + self.page_size - 1) // self.page_size)


def pagination_params(
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[int, int]:
    """Validate and return (page, page_size) with safe defaults.

    Usage:
        page, page_size = pagination_params(page, page_size)
    """
    if page < 1:
        page = DEFAULT_PAGE
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    if page_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE
    return page, page_size
