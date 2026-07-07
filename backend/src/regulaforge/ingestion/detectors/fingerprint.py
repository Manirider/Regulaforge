"""
Document fingerprinting using SHA-256 and simhash.

Provides two fingerprinting strategies:

1. **File integrity** — SHA-256 hash of the raw byte content (identical
   files produce identical hashes).
2. **Semantic similarity** — 64-bit simhash computed from word-level
   features.  Two documents with a Hamming distance below a threshold
   are considered near-duplicates.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from regulaforge.common.exceptions import ValidationError as AppValidationError

SIMHASH_BITS = 64
SIMHASH_HEX_DIGITS = SIMHASH_BITS // 4  # 16
FILE_READ_CHUNK = 8192


@dataclass(frozen=True)
class Fingerprint:
    """Composite fingerprint for a document.

    Attributes:
        file_hash: SHA-256 hex digest of the raw file bytes.
        content_hash: SHA-256 hex digest of the extracted text.
        simhash: 64-bit simhash hex string for similarity comparisons.
        hash_algorithm: Algorithm used for file/content hashing.
    """

    file_hash: str
    content_hash: str
    simhash: str
    hash_algorithm: str = "sha256"

    def to_dict(self) -> dict[str, str]:
        return {
            "file_hash": self.file_hash,
            "content_hash": self.content_hash,
            "simhash": self.simhash,
            "hash_algorithm": self.hash_algorithm,
        }


class SimHashComparator:
    """64-bit simhash implementation for near-duplicate detection.

    Uses MD5 (non-security) as the base hash function for individual words.
    The resulting 64-bit fingerprint can be compared via Hamming distance
    or cosine similarity.
    """

    def compute(self, text: str) -> str:
        """Compute the 64-bit simhash hex string for *text*.

        Args:
            text: Input text (whitespace-tokenised).

        Returns:
            16-character hex string.  For empty or whitespace-only input
            returns ``"0000000000000000"``.
        """
        words = text.split()
        if not words:
            return "0" * SIMHASH_HEX_DIGITS

        v = [0] * SIMHASH_BITS
        for word in words:
            word_hash = self._hash_word(word)
            for i in range(SIMHASH_BITS):
                bit = (word_hash >> i) & 1
                v[i] += 1 if bit else -1

        fingerprint = 0
        for i in range(SIMHASH_BITS):
            if v[i] >= 0:
                fingerprint |= 1 << i

        return f"{fingerprint:016x}"

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """Number of differing bits between two simhash hex strings."""
        try:
            int1 = int(hash1, 16)
            int2 = int(hash2, 16)
        except ValueError:
            raise AppValidationError(
                "Invalid simhash format — expected 16-char hex strings",
                details={"hash1": hash1, "hash2": hash2},
            )
        xor = int1 ^ int2
        return xor.bit_count()

    @staticmethod
    def similarity(hash1: str, hash2: str) -> float:
        """Cosine similarity in [0.0, 1.0] derived from Hamming distance."""
        distance = SimHashComparator.hamming_distance(hash1, hash2)
        return 1.0 - (distance / SIMHASH_BITS)

    @staticmethod
    def _hash_word(word: str) -> int:
        return int(hashlib.md5(word.encode("utf-8"), usedforsecurity=False).hexdigest()[:SIMHASH_HEX_DIGITS], 16)


class FingerprintDetector:
    """Computes file, content, and simhash fingerprints for documents."""

    def __init__(self, simhash_comparator: SimHashComparator | None = None) -> None:
        self._simhash = simhash_comparator or SimHashComparator()

    def compute_file_hash(self, filepath: Path, algorithm: str = "sha256") -> str:
        """SHA-256 (or other) hex digest of the file contents."""
        hasher = hashlib.new(algorithm)
        with open(filepath, "rb") as f:
            while chunk := f.read(FILE_READ_CHUNK):
                hasher.update(chunk)
        return hasher.hexdigest()

    def compute_content_hash(self, content: str, algorithm: str = "sha256") -> str:
        """SHA-256 hex digest of the text content."""
        return hashlib.new(algorithm, content.encode("utf-8")).hexdigest()

    def compute_fingerprint(
        self,
        filepath: Path,
        content: str,
        hash_algorithm: str = "sha256",
    ) -> Fingerprint:
        """Produce a composite ``Fingerprint`` for the given file and text."""
        file_hash = self.compute_file_hash(filepath, hash_algorithm)
        content_hash = self.compute_content_hash(content, hash_algorithm)
        simhash = self._simhash.compute(content)
        return Fingerprint(
            file_hash=file_hash,
            content_hash=content_hash,
            simhash=simhash,
            hash_algorithm=hash_algorithm,
        )
