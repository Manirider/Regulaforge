from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from regulaforge.ingestion.domain.models import CrawlSourceType


@dataclass
class CrawlStarted:
    job_id: UUID
    source_type: CrawlSourceType
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": str(self.job_id),
            "source_type": self.source_type.value,
            "timestamp": self.timestamp.isoformat(),
            "event_type": "crawl_started",
        }


@dataclass
class CrawlCompleted:
    job_id: UUID
    source_type: CrawlSourceType
    documents_found: int
    documents_downloaded: int
    documents_failed: int
    documents_duplicate: int
    duration_seconds: float
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": str(self.job_id),
            "source_type": self.source_type.value,
            "documents_found": self.documents_found,
            "documents_downloaded": self.documents_downloaded,
            "documents_failed": self.documents_failed,
            "documents_duplicate": self.documents_duplicate,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat(),
            "event_type": "crawl_completed",
        }


@dataclass
class DocumentDownloaded:
    document_id: UUID
    source_type: CrawlSourceType
    external_id: str
    title: str
    file_size_bytes: int
    file_hash_sha256: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "source_type": self.source_type.value,
            "external_id": self.external_id,
            "title": self.title,
            "file_size_bytes": self.file_size_bytes,
            "file_hash_sha256": self.file_hash_sha256,
            "timestamp": self.timestamp.isoformat(),
            "event_type": "document_downloaded",
        }


@dataclass
class DocumentDuplicateFound:
    document_id: UUID
    existing_document_id: UUID
    source_type: CrawlSourceType
    external_id: str
    file_hash_sha256: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "existing_document_id": str(self.existing_document_id),
            "source_type": self.source_type.value,
            "external_id": self.external_id,
            "file_hash_sha256": self.file_hash_sha256,
            "timestamp": self.timestamp.isoformat(),
            "event_type": "document_duplicate_found",
        }


@dataclass
class DocumentVersionCreated:
    document_id: UUID
    source_type: CrawlSourceType
    external_id: str
    version: int
    previous_version_id: UUID
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "source_type": self.source_type.value,
            "external_id": self.external_id,
            "version": self.version,
            "previous_version_id": str(self.previous_version_id),
            "timestamp": self.timestamp.isoformat(),
            "event_type": "document_version_created",
        }
