"""
Local-filesystem storage backend with integrity and path-traversal protection.

``LocalStorageBackend`` writes files under a configurable base directory.
Every public operation resolves the relative path through ``Path.resolve()``
and verifies that the resulting absolute path remains within the base
directory, preventing path-traversal attacks.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from regulaforge.ingestion.storage.base import (
    StorageBackend,
    StorageIntegrityError,
    StorageNotFoundError,
    StorageResult,
)

HASH_CHUNK_SIZE = 65536


class LocalStorageBackend(StorageBackend):
    """Stores files under a root directory with integrity verification.

    Args:
        base_path: Root directory for all stored files.
        hash_algorithm: Hash algorithm for integrity checks (default SHA-256).
    """

    def __init__(self, base_path: Path, hash_algorithm: str = "sha256") -> None:
        self.base_path = base_path.resolve()
        self.hash_algorithm = hash_algorithm
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        """Resolve *relative_path* under the base and guard against traversal.

        Raises:
            StorageNotFoundError: If the resolved path is outside the base
                directory (path-traversal attempt).
        """
        candidate = (self.base_path / relative_path).resolve()
        candidate_str = str(candidate)
        base_str = str(self.base_path)
        if not candidate_str.startswith(base_str + "\\") and not candidate_str.startswith(base_str + "/") and candidate_str != base_str:
            if not candidate_str.startswith(base_str):
                raise StorageNotFoundError(f"Path traversal detected: {relative_path}")
        return candidate

    async def store(
        self,
        source_path: Path,
        relative_path: str,
        expected_hash: str | None = None,
        overwrite: bool = False,
    ) -> StorageResult:
        dest = self._resolve(relative_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists() and not overwrite:
            dest_hash = self._hash_file(dest)
            source_hash = self._hash_file(source_path)
            if source_hash != dest_hash:
                raise StorageIntegrityError(
                    f"Destination exists with different content: {relative_path}"
                )
            return StorageResult(
                path=dest,
                size_bytes=source_path.stat().st_size,
                hash_value=source_hash,
                hash_algorithm=self.hash_algorithm,
            )

        shutil.copy2(str(source_path), str(dest))
        actual_hash = self._hash_file(dest)

        if expected_hash and actual_hash != expected_hash:
            dest.unlink(missing_ok=True)
            raise StorageIntegrityError(
                f"Hash mismatch after store: expected {expected_hash}, got {actual_hash}"
            )

        return StorageResult(
            path=dest,
            size_bytes=dest.stat().st_size,
            hash_value=actual_hash,
            hash_algorithm=self.hash_algorithm,
        )

    async def retrieve(self, relative_path: str) -> Path:
        dest = self._resolve(relative_path)
        if not dest.exists():
            raise StorageNotFoundError(f"File not found: {relative_path}")
        return dest

    async def delete(self, relative_path: str) -> None:
        dest = self._resolve(relative_path)
        if dest.exists():
            dest.unlink()

    async def exists(self, relative_path: str) -> bool:
        dest = self._resolve(relative_path)
        return dest.exists()

    async def verify(self, relative_path: str) -> bool:
        try:
            dest = self._resolve(relative_path)
        except StorageNotFoundError:
            return False
        if not dest.exists() or not dest.is_file():
            return False
        try:
            self._hash_file(dest)
            return True
        except (OSError, PermissionError, ValueError):
            return False

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.new(self.hash_algorithm)
        with open(path, "rb") as f:
            while chunk := f.read(HASH_CHUNK_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
