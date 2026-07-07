"""
Pluggable storage backends for the ingestion pipeline.

Provides a common ``StorageBackend`` interface with local-filesystem
and S3-compatible implementations.  Each backend enforces path-traversal
protection and optional hash-verified writes.
"""

from regulaforge.ingestion.storage.base import (
    StorageBackend,
    StorageError,
    StorageResult,
    StorageExistsError,
    StorageNotFoundError,
    StorageIntegrityError,
)
from regulaforge.ingestion.storage.local import LocalStorageBackend

__all__ = [
    "StorageBackend",
    "StorageError",
    "StorageResult",
    "StorageExistsError",
    "StorageNotFoundError",
    "StorageIntegrityError",
    "LocalStorageBackend",
]
