"""
Hash-based file and content integrity verification.

Supports SHA-256 (default), SHA-512, and MD5 (non-security).
"""

from __future__ import annotations

import hashlib
from enum import Enum
from pathlib import Path

HASH_READ_CHUNK = 65536


class HashAlgorithm(Enum):
    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"


class HashVerifier:
    """Verifies file and content integrity against expected hashes."""

    def __init__(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> None:
        self._algorithm = algorithm

    def verify_file(self, filepath: Path, expected_hash: str) -> bool:
        try:
            actual_hash = self.compute_file_hash(filepath, self._algorithm.value)
        except (OSError, PermissionError, FileNotFoundError):
            return False
        return actual_hash == expected_hash

    def verify_content(self, content: str, expected_hash: str) -> bool:
        try:
            actual_hash = self.compute_content_hash(content, self._algorithm.value)
        except (OSError, PermissionError):
            return False
        return actual_hash == expected_hash

    def compute_file_hash(self, filepath: Path, algorithm: str | None = None) -> str:
        alg = algorithm or self._algorithm.value
        hasher = hashlib.new(alg)
        with open(filepath, "rb") as f:
            while chunk := f.read(HASH_READ_CHUNK):
                hasher.update(chunk)
        return hasher.hexdigest()

    def compute_content_hash(self, content: str, algorithm: str | None = None) -> str:
        alg = algorithm or self._algorithm.value
        return hashlib.new(alg, content.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_hash(data: bytes, algorithm: str = "sha256") -> str:
        return hashlib.new(algorithm, data).hexdigest()
