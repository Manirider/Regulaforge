"""SQLAlchemy model for Document entity."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin


class DocumentModel(Base, TimestampMixin):
    """SQLAlchemy model for Document entity."""

    __tablename__ = "documents"

    __table_args__ = (
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
        Index("ix_documents_artifact_type", "artifact_type"),
        Index("ix_documents_processing_status", "processing_status"),
        Index("ix_documents_checksum", "checksum"),
        {
            "comment": "Evidence documents and reference materials",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, comment="Document identifier"
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Document title"
    )
    file_name: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Original file name"
    )
    file_path: Mapped[str] = mapped_column(
        String(2000), nullable=False, comment="Storage path"
    )
    mime_type: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="MIME type"
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="File size in bytes"
    )
    artifact_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Artifact classification"
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, comment="Owning tenant"
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        GUID, nullable=False, comment="Uploading user"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Document description"
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="Searchable tags"
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="File checksum (SHA-256)"
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="Flexible metadata"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Verification status"
    )
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, nullable=True, comment="Verifier user ID"
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Verification timestamp"
    )
    processing_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", comment="AI processing status"
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="AI-extracted text content"
    )

    def __repr__(self) -> str:
        return f"<DocumentModel {self.file_name}>"
