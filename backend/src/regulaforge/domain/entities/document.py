"""Document entity - evidence and reference materials.

Documents serve as evidence artifacts in compliance assessments,
supporting findings and providing proof of compliance.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.entities.base import DomainEntity
from regulaforge.domain.enums import ArtifactType


class Document(DomainEntity):
    """A document associated with a compliance assessment.

    Documents can be uploaded evidence, reference materials,
    policy documents, or any artifact supporting compliance claims.
    """

    def __init__(
        self,
        title: str,
        file_name: str,
        file_path: str,
        mime_type: str,
        file_size_bytes: int,
        artifact_type: ArtifactType,
        tenant_id: UUID,
        uploaded_by: UUID,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        checksum: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._validate(title, file_size_bytes)

        self._title: str = title
        self._file_name: str = file_name
        self._file_path: str = file_path
        self._mime_type: str = mime_type
        self._file_size_bytes: int = file_size_bytes
        self._artifact_type: ArtifactType = artifact_type
        self._tenant_id: UUID = tenant_id
        self._uploaded_by: UUID = uploaded_by
        self._description: Optional[str] = description
        self._tags: list[str] = tags or []
        self._checksum: Optional[str] = checksum
        self._metadata: dict[str, Any] = metadata or {}
        self._is_verified: bool = False
        self._verified_by: Optional[UUID] = None
        self._verified_at: Optional[datetime] = None
        self._processing_status: str = "pending"
        self._extracted_text: Optional[str] = None

    @staticmethod
    def _validate(title: str, file_size_bytes: int) -> None:
        if not title or len(title.strip()) < 2:
            raise ValueError("Document title must be at least 2 characters")
        if file_size_bytes <= 0:
            raise ValueError("File size must be positive")
        if file_size_bytes > 100 * 1024 * 1024:  # 100MB
            raise ValueError("File size exceeds maximum allowed (100MB)")

    @property
    def title(self) -> str:
        return self._title

    @property
    def file_name(self) -> str:
        return self._file_name

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def mime_type(self) -> str:
        return self._mime_type

    @property
    def file_size_bytes(self) -> int:
        return self._file_size_bytes

    @property
    def artifact_type(self) -> ArtifactType:
        return self._artifact_type

    @property
    def tenant_id(self) -> UUID:
        return self._tenant_id

    @property
    def uploaded_by(self) -> UUID:
        return self._uploaded_by

    @property
    def is_verified(self) -> bool:
        return self._is_verified

    @property
    def verified_by(self) -> Optional[UUID]:
        return self._verified_by

    @property
    def verified_at(self) -> Optional[datetime]:
        return self._verified_at

    @property
    def processing_status(self) -> str:
        return self._processing_status

    @property
    def extracted_text(self) -> Optional[str]:
        return self._extracted_text

    def verify(self, verified_by: UUID) -> None:
        """Mark document as verified."""
        if self._is_verified:
            raise ValueError("Document is already verified")
        self._is_verified = True
        self._verified_by = verified_by
        self._verified_at = datetime.now(timezone.utc)
        self.mark_updated(verified_by)

    def mark_processing(self, status: str, extracted_text: Optional[str] = None) -> None:
        """Update document processing status."""
        valid_statuses = {"pending", "processing", "completed", "failed"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid processing status: {status}")
        self._processing_status = status
        if extracted_text:
            self._extracted_text = extracted_text
        self.mark_updated()

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "title": self._title,
            "file_name": self._file_name,
            "file_path": self._file_path,
            "mime_type": self._mime_type,
            "file_size_bytes": self._file_size_bytes,
            "artifact_type": self._artifact_type.value,
            "tenant_id": str(self._tenant_id),
            "uploaded_by": str(self._uploaded_by),
            "description": self._description,
            "tags": self._tags,
            "checksum": self._checksum,
            "is_verified": self._is_verified,
            "verified_by": str(self._verified_by) if self._verified_by else None,
            "verified_at": self._verified_at.isoformat() if self._verified_at else None,
            "processing_status": self._processing_status,
        })
        return base

    def __repr__(self) -> str:
        return f"<Document {self._file_name} [{self._artifact_type.value}]>"
