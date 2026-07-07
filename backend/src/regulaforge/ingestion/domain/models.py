from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


class CrawlSourceType(str, Enum):
    RBI = "rbi"
    SEBI = "sebi"
    IRDAI = "irdai"


class CrawlJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DocumentStatus(str, Enum):
    PENDING_DOWNLOAD = "pending_download"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    PROCESSED = "processed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class DocumentCategory(str, Enum):
    CIRCULAR = "circular"
    MASTER_DIRECTION = "master_direction"
    NOTIFICATION = "notification"
    GUIDELINE = "guideline"
    PRESS_RELEASE = "press_release"
    REPORT = "report"
    AMENDMENT = "amendment"
    OTHER = "other"


@dataclass
class RegulatoryDocument:
    id: UUID
    source_type: CrawlSourceType
    external_id: str
    title: str
    category: DocumentCategory
    url: str
    published_date: datetime
    effective_date: datetime | None = None
    download_path: str | None = None
    file_size_bytes: int | None = None
    file_hash_sha256: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: DocumentStatus = DocumentStatus.PENDING_DOWNLOAD
    version: int = 1
    previous_version_id: UUID | None = None
    checksum_previous: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_downloaded(self, path: str, file_size: int, sha256: str) -> None:
        self.download_path = path
        self.file_size_bytes = file_size
        self.file_hash_sha256 = sha256
        self.status = DocumentStatus.DOWNLOADED
        self.updated_at = datetime.now(timezone.utc)

    def mark_processed(self, content_hash: str, metadata: dict[str, Any]) -> None:
        self.content_hash = content_hash
        self.metadata = metadata
        self.status = DocumentStatus.PROCESSED
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self) -> None:
        self.status = DocumentStatus.FAILED
        self.updated_at = datetime.now(timezone.utc)

    def mark_duplicate(self, existing_id: UUID) -> None:
        self.status = DocumentStatus.DUPLICATE
        self.previous_version_id = existing_id
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "source_type": self.source_type.value,
            "external_id": self.external_id,
            "title": self.title,
            "category": self.category.value,
            "url": self.url,
            "published_date": self.published_date.isoformat(),
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "download_path": self.download_path,
            "file_size_bytes": self.file_size_bytes,
            "file_hash_sha256": self.file_hash_sha256,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "status": self.status.value,
            "version": self.version,
            "previous_version_id": str(self.previous_version_id) if self.previous_version_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CrawlJob:
    id: UUID
    source_type: CrawlSourceType
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: CrawlJobStatus = CrawlJobStatus.PENDING
    documents_found: int = 0
    documents_downloaded: int = 0
    documents_failed: int = 0
    documents_duplicate: int = 0
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def start(self) -> None:
        self.status = CrawlJobStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        self.status = CrawlJobStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        self.status = CrawlJobStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "source_type": self.source_type.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "documents_found": self.documents_found,
            "documents_downloaded": self.documents_downloaded,
            "documents_failed": self.documents_failed,
            "documents_duplicate": self.documents_duplicate,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DocumentFingerprint:
    id: UUID
    document_id: UUID
    file_hash_sha256: str
    content_hash: str
    simhash: int | None = None
    num_tokens: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CrawlSourceConfig:
    source_type: CrawlSourceType
    base_url: str
    list_url: str
    enabled: bool = True
    crawl_interval_minutes: int = 360
    user_agent: str = "RegulaForge/2.0 (+https://regulaforge.io)"
    request_timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    concurrent_downloads: int = 4
