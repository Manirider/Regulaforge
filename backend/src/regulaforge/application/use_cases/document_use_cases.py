"""Document management use cases.

Handles the complete lifecycle of documents from upload
through verification, search, and deletion.
"""

import hashlib
import os
from typing import Any, Optional
from uuid import UUID

from regulaforge.application.use_cases.base import UseCase
from regulaforge.config.constants import ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE_MB, ArtifactType
from regulaforge.domain.entities.document import Document
from regulaforge.domain.events.document import DocumentDeleted, DocumentUploaded, DocumentVerified
from regulaforge.domain.repositories.base import EntityNotFoundError
from regulaforge.domain.repositories.document_repository import DocumentRepository


class UploadDocumentUseCase(UseCase):
    """Use case for uploading a new document."""

    def __init__(self, document_repo: DocumentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._document_repo = document_repo

    async def execute(
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
        metadata: Optional[dict[str, Any]] = None,
    ) -> Document:
        """Upload a new document.

        Validates the file extension, size, and computes a
        SHA-256 checksum for integrity verification.

        Args:
            title: Document title.
            file_name: Original file name.
            file_path: Storage path for the file.
            mime_type: MIME type of the file.
            file_size_bytes: File size in bytes.
            artifact_type: Type of evidence artifact.
            tenant_id: Tenant this document belongs to.
            uploaded_by: User uploading the document.
            description: Optional description.
            tags: Optional searchable tags.
            metadata: Optional flexible metadata.

        Returns:
            The created Document.

        Raises:
            ValueError: If file validation fails.
        """
        self.logger.info(
            "Uploading document: title=%s file=%s type=%s tenant=%s",
            title, file_name, artifact_type.value, tenant_id,
        )

        # Validate file extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise ValueError(
                f"File extension '{ext}' is not allowed. "
                f"Allowed: {', '.join(ALLOWED_UPLOAD_EXTENSIONS)}"
            )

        # Validate file size
        max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size_bytes > max_bytes:
            raise ValueError(
                f"File size {file_size_bytes} bytes exceeds maximum "
                f"allowed size of {MAX_UPLOAD_SIZE_MB}MB"
            )

        # Compute checksum from file content
        checksum = await self._compute_checksum(file_path)

        # Check for duplicate by checksum
        existing = await self._document_repo.get_by_checksum(checksum)
        if existing:
            self.logger.warning(
                "Duplicate document detected: checksum=%s existing=%s",
                checksum, existing.id,
            )

        document = Document(
            title=title,
            file_name=file_name,
            file_path=file_path,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            artifact_type=artifact_type,
            tenant_id=tenant_id,
            uploaded_by=uploaded_by,
            description=description,
            tags=tags,
            checksum=checksum,
            metadata=metadata,
        )

        saved = await self._document_repo.save(document)
        await self._publish_event(DocumentUploaded(
            document_id=saved.id,
            file_name=saved.file_name,
            artifact_type=saved.artifact_type.value,
            tenant_id=saved.tenant_id,
        ))
        self.logger.info("Document uploaded: id=%s file=%s", saved.id, file_name)
        return saved

    async def _compute_checksum(self, file_path: str) -> str:
        """Compute SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
        except FileNotFoundError:
            self.logger.warning("File not found for checksum: %s", file_path)
            return ""
        return sha256.hexdigest()


class GetDocumentUseCase(UseCase):
    """Use case for retrieving a document."""

    def __init__(self, document_repo: DocumentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._document_repo = document_repo

    async def execute(self, document_id: UUID) -> Document:
        document = await self._document_repo.get_by_id(document_id)
        if not document:
            raise EntityNotFoundError("Document", document_id)
        return document


class VerifyDocumentUseCase(UseCase):
    """Use case for verifying a document."""

    def __init__(self, document_repo: DocumentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._document_repo = document_repo

    async def execute(self, document_id: UUID, verified_by: UUID) -> Document:
        """Mark a document as verified.

        Args:
            document_id: The document UUID.
            verified_by: User verifying the document.

        Returns:
            The updated Document.

        Raises:
            EntityNotFoundError: If document not found.
            ValueError: If document is already verified.
        """
        self.logger.info("Verifying document: id=%s", document_id)

        document = await self._document_repo.get_by_id(document_id)
        if not document:
            raise EntityNotFoundError("Document", document_id)

        document.verify(verified_by)
        saved = await self._document_repo.save(document)

        await self._publish_event(DocumentVerified(
            document_id=saved.id,
            file_name=saved.file_name,
            verified_by=verified_by,
        ))

        self.logger.info("Document verified: id=%s", document_id)
        return saved


class SearchDocumentsUseCase(UseCase):
    """Use case for searching documents."""

    def __init__(self, document_repo: DocumentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._document_repo = document_repo

    async def execute(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        return await self._document_repo.search(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )


class DeleteDocumentUseCase(UseCase):
    """Use case for deleting a document."""

    def __init__(self, document_repo: DocumentRepository, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._document_repo = document_repo

    async def execute(
        self, document_id: UUID, hard_delete: bool = False
    ) -> None:
        """Delete a document.

        Args:
            document_id: The document UUID.
            hard_delete: If True, permanently remove from storage.
                         If False, perform a soft delete.

        Raises:
            EntityNotFoundError: If document not found.
        """
        self.logger.info(
            "Deleting document: id=%s hard=%s", document_id, hard_delete,
        )

        document = await self._document_repo.get_by_id(document_id)
        if not document:
            raise EntityNotFoundError("Document", document_id)

        file_name = document.file_name

        if hard_delete:
            # Remove file from storage if it exists
            try:
                if os.path.exists(document.file_path):
                    os.remove(document.file_path)
                    self.logger.debug("Deleted file: %s", document.file_path)
            except OSError as e:
                self.logger.warning("Failed to delete file %s: %s", document.file_path, e)

        await self._document_repo.delete(document_id)

        await self._publish_event(DocumentDeleted(
            document_id=document_id,
            file_name=file_name,
        ))

        self.logger.info("Document deleted: id=%s hard=%s", document_id, hard_delete)
