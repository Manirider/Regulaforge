import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin


class CrawlJobModel(Base, TimestampMixin):
    __tablename__ = "crawl_jobs"

    __table_args__ = (
        Index("ix_crawl_jobs_source_type", "source_type"),
        Index("ix_crawl_jobs_status", "status"),
        Index("ix_crawl_jobs_created_at", "created_at"),
        {"comment": "Regulatory crawl job tracking"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Job identifier"
    )
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Regulatory source (rbi, sebi, irdai)"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Crawl start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Crawl end timestamp"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="Job status"
    )
    documents_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Documents discovered"
    )
    documents_downloaded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Documents downloaded"
    )
    documents_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Documents failed"
    )
    documents_duplicate: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Duplicate documents skipped"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Error details if failed"
    )


class RegulatoryDocumentModel(Base, TimestampMixin):
    __tablename__ = "regulatory_documents"

    __table_args__ = (
        Index("ix_regdocs_source_external", "source_type", "external_id"),
        Index("ix_regdocs_source_type", "source_type"),
        Index("ix_regdocs_status", "status"),
        Index("ix_regdocs_published_date", "published_date"),
        Index("ix_regdocs_file_hash", "file_hash_sha256"),
        Index("ix_regdocs_content_hash", "content_hash"),
        {"comment": "Regulatory documents ingested from Indian regulators"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Document identifier"
    )
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Regulatory source"
    )
    external_id: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Source-specific identifier"
    )
    title: Mapped[str] = mapped_column(
        String(1000), nullable=False, comment="Document title"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="other", comment="Document category"
    )
    url: Mapped[str] = mapped_column(
        String(2000), nullable=False, comment="Source URL"
    )
    published_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Publication date"
    )
    effective_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Effective/implementation date"
    )
    download_path: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True, comment="Local storage path"
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="File size in bytes"
    )
    file_hash_sha256: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="SHA-256 of raw file"
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="SHA-256 of normalized text"
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="Extracted metadata"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending_download", comment="Processing status"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Document version number"
    )
    previous_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Previous version document ID"
    )


class DocumentFingerprintModel(Base, TimestampMixin):
    __tablename__ = "document_fingerprints"

    __table_args__ = (
        Index("ix_fingerprints_document_id", "document_id"),
        Index("ix_fingerprints_file_hash", "file_hash_sha256"),
        Index("ix_fingerprints_content_hash", "content_hash"),
        {"comment": "Document fingerprints for deduplication"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Fingerprint identifier"
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, comment="Regulatory document ID"
    )
    file_hash_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 of raw file"
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 of normalized text"
    )
    simhash: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="SimHash fingerprint (64-bit)"
    )
    num_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Number of tokens"
    )
