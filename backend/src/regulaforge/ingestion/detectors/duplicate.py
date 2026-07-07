"""
Multi-level duplicate detection for regulatory documents.

Checks against existing fingerprints in three progressively broader ways:

1. **EXACT_FILE** — identical SHA-256 file hash.
2. **EXACT_CONTENT** — identical SHA-256 content hash.
3. **NEAR_DUPLICATE** — simhash similarity above a configurable threshold.

The first match short-circuits evaluation.  Title/date matching is performed
upstream by the orchestrator where document metadata is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from regulaforge.ingestion.detectors.fingerprint import (
    Fingerprint,
    FingerprintDetector,
    SimHashComparator,
)
from regulaforge.ingestion.domain.models import DocumentFingerprint

DEFAULT_SIMHASH_THRESHOLD = 0.85


class DuplicateLevel(Enum):
    """Specificity level of a duplicate match."""

    EXACT_FILE = "exact_file"
    EXACT_CONTENT = "exact_content"
    NEAR_DUPLICATE = "near_duplicate"
    NOT_DUPLICATE = "not_duplicate"


@dataclass
class DuplicateResult:
    """Result of a duplicate check against existing fingerprints.

    Attributes:
        is_duplicate: True if a match was found at any level.
        level: The most specific matching level.
        matched_fingerprint_id: ID of the matched fingerprint, if any.
        similarity_score: Similarity score (1.0 for exact, [0,1] for simhash).
        details: Debugging context with hash values and similarity.
    """

    is_duplicate: bool
    level: DuplicateLevel
    matched_fingerprint_id: str | None = None
    similarity_score: float = 0.0
    details: dict[str, object] = field(default_factory=dict)


class DuplicateDetector:
    """Checks a new document against a list of existing fingerprints.

    The caller is responsible for fetching the relevant fingerprints from
    the repository.  This class is stateless and thread-safe.
    """

    def __init__(
        self,
        fingerprint_detector: FingerprintDetector | None = None,
        simhash_threshold: float = DEFAULT_SIMHASH_THRESHOLD,
    ) -> None:
        self._fingerprint = fingerprint_detector or FingerprintDetector()
        self._simhash_comparator = SimHashComparator()
        self._simhash_threshold = simhash_threshold

    async def check_duplicate(
        self,
        filepath: Path,
        content: str,
        existing_fingerprints: list[DocumentFingerprint],
    ) -> DuplicateResult:
        """Check whether a document is a duplicate of any known document.

        Args:
            filepath: Path to the downloaded file (for file-hash computation).
            content: Extracted text content.
            existing_fingerprints: Fingerprints of previously processed documents.

        Returns:
            A ``DuplicateResult`` describing the first match found, or
            ``NOT_DUPLICATE`` if no match exists.
        """
        current_fp = self._fingerprint.compute_fingerprint(filepath, content)

        for existing in existing_fingerprints:
            result = self._compare_with_existing(current_fp, existing)
            if result.is_duplicate:
                return result

        return DuplicateResult(is_duplicate=False, level=DuplicateLevel.NOT_DUPLICATE)

    def _compare_with_existing(
        self,
        current: Fingerprint,
        existing: DocumentFingerprint,
    ) -> DuplicateResult:
        details: dict[str, object] = {
            "current_file_hash": current.file_hash,
            "existing_file_hash": existing.file_hash_sha256,
            "current_content_hash": current.content_hash,
            "existing_content_hash": existing.content_hash,
        }

        if existing.file_hash_sha256 and current.file_hash == existing.file_hash_sha256:
            return DuplicateResult(
                is_duplicate=True,
                level=DuplicateLevel.EXACT_FILE,
                matched_fingerprint_id=str(existing.id),
                similarity_score=1.0,
                details=details,
            )

        if existing.content_hash and current.content_hash == existing.content_hash:
            return DuplicateResult(
                is_duplicate=True,
                level=DuplicateLevel.EXACT_CONTENT,
                matched_fingerprint_id=str(existing.id),
                similarity_score=1.0,
                details=details,
            )

        simhash_similarity: float = 0.0
        if existing.simhash is not None:
            existing_simhash_hex = f"{existing.simhash:016x}"
            simhash_similarity = self._simhash_comparator.similarity(
                current.simhash, existing_simhash_hex
            )
            details["simhash_similarity"] = simhash_similarity
            if simhash_similarity >= self._simhash_threshold:
                return DuplicateResult(
                    is_duplicate=True,
                    level=DuplicateLevel.NEAR_DUPLICATE,
                    matched_fingerprint_id=str(existing.id),
                    similarity_score=simhash_similarity,
                    details=details,
                )

        return DuplicateResult(
            is_duplicate=False,
            level=DuplicateLevel.NOT_DUPLICATE,
            similarity_score=simhash_similarity,
            details=details,
        )
