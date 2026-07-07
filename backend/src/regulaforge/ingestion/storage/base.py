from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class StorageError(Exception):
    pass


class StorageExistsError(StorageError):
    pass


class StorageNotFoundError(StorageError):
    pass


class StorageIntegrityError(StorageError):
    pass


@dataclass
class StorageResult:
    path: Path
    size_bytes: int
    hash_value: str
    hash_algorithm: str
    success: bool = True
    error: str | None = None


class StorageBackend(ABC):
    @abstractmethod
    async def store(
        self,
        source_path: Path,
        relative_path: str,
        expected_hash: str | None = None,
        overwrite: bool = False,
    ) -> StorageResult:
        ...

    @abstractmethod
    async def retrieve(self, relative_path: str) -> Path:
        ...

    @abstractmethod
    async def delete(self, relative_path: str) -> None:
        ...

    @abstractmethod
    async def exists(self, relative_path: str) -> bool:
        ...

    @abstractmethod
    async def verify(self, relative_path: str) -> bool:
        ...
