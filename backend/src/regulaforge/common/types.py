"""Shared type aliases, protocols, and generic type definitions."""

from __future__ import annotations

from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    Union,
)
from uuid import UUID


T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


JSONPrimitive = Union[str, int, float, bool, None]
JSONArray = List["JSONSerializable"]
JSONObject = Dict[str, "JSONSerializable"]
JSONSerializable = Union[JSONPrimitive, JSONArray, JSONObject]
"""Type alias for JSON-serializable values."""


ID = Union[str, int, UUID]
"""Type alias for entity identifiers."""


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class PaginatedResult(Sequence[T]):
    """Generic paginated result wrapper."""

    def __init__(
        self,
        items: List[T],
        total: int,
        page: int = 1,
        size: int = 20,
    ) -> None:
        self._items = items
        self.total = total
        self.page = page
        self.size = size

    @property
    def items(self) -> List[T]:
        return self._items

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.size)) if self.size else 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    def __getitem__(self, index: int) -> T:
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __repr__(self) -> str:
        return (
            f"PaginatedResult(total={self.total}, page={self.page}, "
            f"size={self.size}, items={len(self._items)})"
        )


class EntityDict(Dict[str, Any]):
    """A dictionary representation of a domain entity."""

    pass


class LoggerProtocol(Protocol):
    """Protocol for logger-compatible objects."""

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...


class AsyncRepository(Protocol[T_co]):
    """Protocol for async repositories."""

    async def get(self, id: ID) -> Optional[T_co]:
        ...

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        **filters: Any,
    ) -> PaginatedResult[T_co]:
        ...

    async def create(self, entity: T_co) -> T_co:
        ...

    async def update(self, id: ID, data: EntityDict) -> T_co:
        ...

    async def delete(self, id: ID) -> None:
        ...


class AsyncUnitOfWork(Protocol):
    """Protocol for unit of work pattern."""

    async def __aenter__(self) -> AsyncUnitOfWork:
        ...

    async def __aexit__(
        self,
        exc_type: type,
        exc_val: Exception,
        exc_tb: object,
    ) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


class AsyncIterableProtocol(Protocol[T_co]):
    """Protocol for async iterables."""

    def __aiter__(self) -> AsyncIterator[T_co]:
        ...


__all__ = [
    "T",
    "T_co",
    "JSONPrimitive",
    "JSONArray",
    "JSONObject",
    "JSONSerializable",
    "ID",
    "SortOrder",
    "PaginatedResult",
    "EntityDict",
    "LoggerProtocol",
    "AsyncRepository",
    "AsyncUnitOfWork",
    "AsyncIterableProtocol",
]
