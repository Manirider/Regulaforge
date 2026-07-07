"""Document management API endpoints.

Handles document upload, retrieval, verification, search,
and deletion for compliance evidence artifacts.
"""

import contextlib
import json
import os
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, Response

from regulaforge.application.use_cases.document_use_cases import (
    DeleteDocumentUseCase,
    GetDocumentUseCase,
    SearchDocumentsUseCase,
    UploadDocumentUseCase,
    VerifyDocumentUseCase,
)
from regulaforge.config.constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
    MAX_PAGE_SIZE,
    MAX_UPLOAD_SIZE_MB,
    ArtifactType,
)
from regulaforge.domain.repositories.base import EntityNotFoundError
from regulaforge.interfaces.api.dependencies import (
    get_current_user_id,
    get_delete_document_uc,
    get_get_document_uc,
    get_search_documents_uc,
    get_upload_document_uc,
    get_verify_document_uc,
)
from regulaforge.interfaces.api.v1.schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentVerifyRequest,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=DocumentResponse, status_code=HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(..., description="File to upload"),  # noqa: B008
    title: str = Form(..., min_length=2, max_length=500, description="Document title"),
    artifact_type: ArtifactType = Form(..., description="Type of evidence artifact"),  # noqa: B008
    tenant_id: UUID = Form(..., description="Tenant ID"),  # noqa: B008
    description: Optional[str] = Form(default=None, description="Document description"),
    tags: Optional[str] = Form(default=None, description="Comma-separated tags"),
    metadata: Optional[str] = Form(default=None, description="JSON metadata string"),
    use_case: UploadDocumentUseCase = Depends(get_upload_document_uc),  # noqa: B008
    current_user_id: UUID = Depends(get_current_user_id),  # noqa: B008
) -> Any:
    """Upload a new compliance evidence document.

    Accepts multipart file upload with metadata fields.
    Validates file extension and size before processing.
    """
    # Validate content length before reading
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content_length = file.headers.get("content-length")
    if content_length is not None and int(content_length) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large — content-length {content_length} bytes exceeds maximum of {MAX_UPLOAD_SIZE_MB}MB",
        )

    # Validate file extension
    ext = f".{file.filename.split('.')[-1].lower()}" if "." in file.filename else ""
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is not allowed. Allowed: {', '.join(ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    if file_size > max_bytes:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"File size {file_size} bytes exceeds maximum allowed size of {MAX_UPLOAD_SIZE_MB}MB",
        )

    # Save file to storage
    storage_dir = os.path.join("storage", "documents", str(tenant_id))
    os.makedirs(storage_dir, exist_ok=True)

    storage_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{current_user_id}_{file.filename}"
    file_path = os.path.join(storage_dir, storage_name)

    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except OSError as e:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e}",
        )

    # Parse optional fields
    parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    parsed_metadata = None
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Invalid metadata JSON: {e}",
            )

    try:
        document = await use_case.execute(
            title=title,
            file_name=file.filename,
            file_path=file_path,
            mime_type=file.content_type or "application/octet-stream",
            file_size_bytes=file_size,
            artifact_type=artifact_type,
            tenant_id=tenant_id,
            uploaded_by=current_user_id,
            description=description,
            tags=parsed_tags,
            metadata=parsed_metadata,
        )
        return _document_to_response(document)
    except ValueError as e:
        # Clean up saved file on validation failure
        with contextlib.suppress(OSError):
            os.remove(file_path)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    tenant_id: Optional[UUID] = Query(default=None, description="Filter by tenant ID"),  # noqa: B008
    artifact_type: Optional[str] = Query(default=None, description="Filter by artifact type"),
    processing_status: Optional[str] = Query(default=None, description="Filter by processing status"),
    is_verified: Optional[bool] = Query(default=None, description="Filter by verification status"),
    sort_by: Optional[str] = Query(default=None, description="Sort field"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order"),
    use_case: SearchDocumentsUseCase = Depends(get_search_documents_uc),  # noqa: B008
) -> Any:
    """List documents with filtering and pagination."""
    filters = {}
    if tenant_id:
        filters["tenant_id"] = tenant_id
    if artifact_type:
        filters["artifact_type"] = artifact_type
    if processing_status:
        filters["processing_status"] = processing_status
    if is_verified is not None:
        filters["is_verified"] = is_verified

    documents, total = await use_case.execute(
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, -(-total // page_size))

    return DocumentListResponse(
        items=[_document_to_response(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    use_case: GetDocumentUseCase = Depends(get_get_document_uc),  # noqa: B008
) -> Any:
    """Get a document by its ID."""
    try:
        document = await use_case.execute(document_id)
        return _document_to_response(document)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{document_id}/verify", response_model=DocumentResponse)
async def verify_document(
    document_id: UUID,
    request: DocumentVerifyRequest,
    use_case: VerifyDocumentUseCase = Depends(get_verify_document_uc),  # noqa: B008
) -> Any:
    """Verify a document, confirming its authenticity and integrity."""
    try:
        document = await use_case.execute(
            document_id=document_id,
            verified_by=request.verified_by,
        )
        return _document_to_response(document)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{document_id}", status_code=HTTP_204_NO_CONTENT, response_class=Response)
async def delete_document(
    document_id: UUID,
    hard_delete: bool = Query(default=False, description="Permanently delete file from storage"),
    use_case: DeleteDocumentUseCase = Depends(get_delete_document_uc),  # noqa: B008
) -> Response:
    """Delete a document.

    Performs a soft delete by default. Use hard_delete=true
    to permanently remove the file from storage.
    """
    try:
        await use_case.execute(
            document_id=document_id,
            hard_delete=hard_delete,
        )
        return Response(status_code=HTTP_204_NO_CONTENT)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _document_to_response(document: Any) -> dict[str, Any]:
    """Convert a Document domain entity to API response."""
    data = document.to_dict()
    return DocumentResponse(
        id=data["id"],
        title=data["title"],
        file_name=data["file_name"],
        file_path=data["file_path"],
        mime_type=data["mime_type"],
        file_size_bytes=data["file_size_bytes"],
        artifact_type=data["artifact_type"],
        tenant_id=data["tenant_id"],
        uploaded_by=data["uploaded_by"],
        description=data.get("description"),
        tags=data.get("tags", []),
        checksum=data.get("checksum"),
        is_verified=data.get("is_verified", False),
        verified_by=data.get("verified_by"),
        verified_at=data.get("verified_at"),
        processing_status=data.get("processing_status", "pending"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )
