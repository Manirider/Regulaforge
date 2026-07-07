"""
Version-change detection for regulatory documents.

Compares a current ``DocumentSnapshot`` against a previous one to classify
the type of change (new document, content changed, metadata changed, or
no change).  This drives version-bumping logic in the pipeline orchestrator.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from regulaforge.ingestion.detectors.fingerprint import FingerprintDetector


class ChangeType(Enum):
    NEW_DOCUMENT = "new_document"
    CONTENT_CHANGED = "content_changed"
    METADATA_CHANGED = "metadata_changed"
    NO_CHANGE = "no_change"


@dataclass
class VersionChange:
    change_type: ChangeType
    document_id: str | None = None
    previous_hash: str | None = None
    current_hash: str | None = None
    changed_fields: list[str] = field(default_factory=list)
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class DocumentSnapshot:
    """Immutable snapshot of a document at a point in time."""

    external_id: str
    title: str
    file_hash: str
    content_hash: str
    category: str
    source_type: str
    publication_date: str | None
    file_size_bytes: int | None
    metadata_hash: str | None = None


class VersionDetector:
    """Compares document snapshots to determine version changes."""

    def __init__(self, fingerprint_detector: FingerprintDetector | None = None) -> None:
        self._fingerprint = fingerprint_detector or FingerprintDetector()

    def detect_change(
        self,
        current: DocumentSnapshot,
        previous: DocumentSnapshot | None,
    ) -> VersionChange:
        """Compare two document snapshots.

        Args:
            current: The newly fetched document snapshot.
            previous: The previously stored snapshot, or None for new docs.

        Returns:
            A ``VersionChange`` describing the type and scope of change.
        """
        if previous is None:
            return VersionChange(
                change_type=ChangeType.NEW_DOCUMENT,
                details={"reason": "No previous version exists"},
            )

        changed_fields: list[str] = []
        for field_name in ("file_hash", "content_hash", "title", "category", "publication_date", "file_size_bytes"):
            current_val = getattr(current, field_name, None)
            previous_val = getattr(previous, field_name, None)
            if current_val != previous_val:
                changed_fields.append(field_name)

        if current.metadata_hash and previous.metadata_hash and current.metadata_hash != previous.metadata_hash:
            changed_fields.append("metadata")

        if current.file_hash != previous.file_hash:
            return VersionChange(
                change_type=ChangeType.CONTENT_CHANGED,
                previous_hash=previous.file_hash,
                current_hash=current.file_hash,
                changed_fields=changed_fields,
                details={"changed_fields": changed_fields},
            )

        if current.content_hash != previous.content_hash:
            return VersionChange(
                change_type=ChangeType.CONTENT_CHANGED,
                previous_hash=previous.content_hash,
                current_hash=current.content_hash,
                changed_fields=changed_fields,
                details={"changed_fields": changed_fields},
            )

        if changed_fields:
            return VersionChange(
                change_type=ChangeType.METADATA_CHANGED,
                changed_fields=changed_fields,
                details={"changed_fields": changed_fields},
            )

        return VersionChange(
            change_type=ChangeType.NO_CHANGE,
            changed_fields=[],
            details={"reason": "No changes detected"},
        )

    def compute_snapshot(
        self,
        external_id: str,
        title: str,
        file_path: str,
        content: str,
        category: str,
        source_type: str,
        publication_date: str | None = None,
        file_size_bytes: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> DocumentSnapshot:
        """Build a ``DocumentSnapshot`` from raw document attributes.

        Args:
            external_id: Source-specific document identifier.
            title: Document title.
            file_path: Absolute path to the downloaded file on disk.
            content: Extracted text content.
            category: Document category (e.g. "circular", "guideline").
            source_type: Source identifier (e.g. "rbi", "sebi").
            publication_date: ISO publication date string.
            file_size_bytes: Size of the downloaded file.
            metadata: Arbitrary key-value metadata for change detection.

        Returns:
            A fully populated ``DocumentSnapshot``.
        """
        fp = self._fingerprint.compute_fingerprint(Path(file_path), content)

        metadata_hash: str | None = None
        if metadata:
            serialized = json.dumps(metadata, sort_keys=True)
            metadata_hash = hashlib.sha256(serialized.encode()).hexdigest()

        return DocumentSnapshot(
            external_id=external_id,
            title=title,
            file_hash=fp.file_hash,
            content_hash=fp.content_hash,
            category=category,
            source_type=source_type,
            publication_date=publication_date,
            file_size_bytes=file_size_bytes,
            metadata_hash=metadata_hash,
        )
