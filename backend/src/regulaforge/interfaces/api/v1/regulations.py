"""Regulation management API endpoints.

Handles CRUD and lifecycle operations for regulations,
including requirements management and search.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from regulaforge.application.use_cases.regulation_use_cases import (
    AddRequirementUseCase,
    CreateRegulationUseCase,
    GetRegulationUseCase,
    PublishRegulationUseCase,
    SearchRegulationsUseCase,
    UpdateRegulationUseCase,
)
from regulaforge.config.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    MAX_PAGE_SIZE,
)
from regulaforge.domain.entities.user import User
from regulaforge.domain.repositories.base import DuplicateEntityError, EntityNotFoundError
from regulaforge.interfaces.api.dependencies import (
    get_add_requirement_uc,
    get_create_regulation_uc,
    get_get_regulation_uc,
    get_publish_regulation_uc,
    get_search_regulations_uc,
    get_update_regulation_uc,
)
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user
from regulaforge.interfaces.api.v1.schemas import (
    RegulationCreateRequest,
    RegulationListResponse,
    RegulationResponse,
    RegulationUpdateRequest,
    RequirementCreateRequest,
)

router = APIRouter(prefix="/regulations", tags=["Regulations"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=RegulationResponse, status_code=HTTP_201_CREATED)
async def create_regulation(
    request: RegulationCreateRequest,
    use_case: CreateRegulationUseCase = Depends(get_create_regulation_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Create a new regulation.

    Registers a regulatory document, law, or standard in the system.
    The regulation starts in 'draft' status and must be published
    before it can be used in assessments.
    """
    try:
        regulation = await use_case.execute(
            title=request.title,
            code=request.code,
            description=request.description,
            category=request.category,
            jurisdiction=request.jurisdiction,
            issuing_body=request.issuing_body,
            effective_date=request.effective_date,
            created_by=current_user.id,
            tags=request.tags,
            parent_regulation_id=request.parent_regulation_id,
            metadata=request.metadata,
        )
        return _regulation_to_response(regulation)
    except DuplicateEntityError as e:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=RegulationListResponse)
async def list_regulations(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    jurisdiction: Optional[str] = Query(default=None, description="Filter by jurisdiction"),
    search: Optional[str] = Query(default=None, description="Full-text search"),
    sort_by: Optional[str] = Query(default=None, description="Sort field"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order"),
    use_case: SearchRegulationsUseCase = Depends(get_search_regulations_uc),  # noqa: B008
) -> Any:
    """List regulations with filtering, search, and pagination."""
    filters = {}
    if status:
        filters["status"] = status
    if category:
        filters["category"] = category
    if jurisdiction:
        filters["jurisdiction"] = jurisdiction

    if search:
        filters["search"] = search

    regulations, total = await use_case.execute(
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, -(-total // page_size))  # Ceiling division

    return RegulationListResponse(
        items=[_regulation_to_response(r) for r in regulations],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{regulation_id}", response_model=RegulationResponse)
async def get_regulation(
    regulation_id: UUID,
    use_case: GetRegulationUseCase = Depends(get_get_regulation_uc),  # noqa: B008
) -> Any:
    """Get a regulation by its ID."""
    try:
        regulation = await use_case.execute(regulation_id)
        return _regulation_to_response(regulation)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch("/{regulation_id}", response_model=RegulationResponse)
async def update_regulation(
    regulation_id: UUID,
    request: RegulationUpdateRequest,
    use_case: UpdateRegulationUseCase = Depends(get_update_regulation_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Update an existing regulation."""
    try:
        updates = request.model_dump(exclude_none=True)
        regulation = await use_case.execute(
            regulation_id=regulation_id,
            updated_by=current_user.id,
            **updates,
        )
        return _regulation_to_response(regulation)
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


@router.post("/{regulation_id}/publish", response_model=RegulationResponse)
async def publish_regulation(
    regulation_id: UUID,
    use_case: PublishRegulationUseCase = Depends(get_publish_regulation_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Publish a draft regulation, making it active for assessments."""
    try:
        regulation = await use_case.execute(
            regulation_id=regulation_id,
            published_by=current_user.id,
        )
        return _regulation_to_response(regulation)
    except (EntityNotFoundError, ValueError) as e:
        status_code = HTTP_404_NOT_FOUND if isinstance(e, EntityNotFoundError) else HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/{regulation_id}/requirements", response_model=RegulationResponse)
async def add_requirement(
    regulation_id: UUID,
    request: RequirementCreateRequest,
    use_case: AddRequirementUseCase = Depends(get_add_requirement_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Add a requirement to a regulation."""
    try:
        regulation = await use_case.execute(
            regulation_id=regulation_id,
            code=request.code,
            title=request.title,
            description=request.description,
            is_mandatory=request.is_mandatory,
            risk_weight=request.risk_weight,
            guidance=request.guidance,
            references=request.references,
            parent_requirement_code=request.parent_requirement_code,
            added_by=current_user.id,
        )
        return _regulation_to_response(regulation)
    except (EntityNotFoundError, ValueError) as e:
        status_code = HTTP_404_NOT_FOUND if isinstance(e, EntityNotFoundError) else HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _regulation_to_response(regulation: Any) -> dict[str, Any]:
    """Convert a Regulation domain entity to API response."""
    data = regulation.to_dict()
    return RegulationResponse(
        id=data["id"],
        title=data["title"],
        code=data["code"],
        description=data["description"],
        category=data["category"],
        jurisdiction=data["jurisdiction"],
        issuing_body=data["issuing_body"],
        effective_date=data["effective_date"],
        status=data["status"],
        version=data["version"],
        tags=data["tags"],
        parent_regulation_id=data.get("parent_regulation_id"),
        superseded_by_id=data.get("superseded_by_id"),
        requirements=data.get("requirements", []),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )
