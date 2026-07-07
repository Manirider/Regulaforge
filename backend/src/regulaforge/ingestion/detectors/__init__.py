"""
Detection services for document fingerprinting, deduplication, version
tracking, and hash-based integrity verification.

These are domain-agnostic algorithms that operate on document content and
metadata without side effects.  They are used by the pipeline orchestration
layer to make decisions about duplicate avoidance, version bumping, and
integrity enforcement.
"""

from regulaforge.ingestion.detectors.fingerprint import (
    Fingerprint,
    FingerprintDetector,
    SimHashComparator,
)
from regulaforge.ingestion.detectors.duplicate import (
    DuplicateDetector,
    DuplicateResult,
    DuplicateLevel,
)
from regulaforge.ingestion.detectors.version import (
    VersionDetector,
    VersionChange,
    ChangeType,
)
from regulaforge.ingestion.detectors.hash_verifier import HashVerifier, HashAlgorithm

__all__ = [
    "Fingerprint",
    "FingerprintDetector",
    "SimHashComparator",
    "DuplicateDetector",
    "DuplicateResult",
    "DuplicateLevel",
    "VersionDetector",
    "VersionChange",
    "ChangeType",
    "HashVerifier",
    "HashAlgorithm",
]
