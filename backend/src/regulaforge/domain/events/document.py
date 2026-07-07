"""Document domain events."""

from typing import Any
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class DocumentUploaded(DomainEvent):
    """Emitted when a new document is uploaded."""

    def __init__(self, document_id: UUID, file_name: str, artifact_type: str, tenant_id: UUID, **kwargs: Any) -> None:
        super().__init__(
            event_type="document.uploaded",
            aggregate_id=document_id,
            aggregate_type="document",
            data={
                "file_name": file_name,
                "artifact_type": artifact_type,
                "tenant_id": str(tenant_id),
            },
            **kwargs,
        )


class DocumentVerified(DomainEvent):
    """Emitted when a document is verified."""

    def __init__(self, document_id: UUID, file_name: str, verified_by: UUID, **kwargs: Any) -> None:
        super().__init__(
            event_type="document.verified",
            aggregate_id=document_id,
            aggregate_type="document",
            data={
                "file_name": file_name,
                "verified_by": str(verified_by),
            },
            **kwargs,
        )


class DocumentDeleted(DomainEvent):
    """Emitted when a document is deleted."""

    def __init__(self, document_id: UUID, file_name: str, **kwargs: Any) -> None:
        super().__init__(
            event_type="document.deleted",
            aggregate_id=document_id,
            aggregate_type="document",
            data={"file_name": file_name},
            **kwargs,
        )
