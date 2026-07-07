"""Entity management API endpoints.

Handles CRUD, lifecycle, and hierarchy operations for
assessable entities within a tenant context.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from regulaforge.application.use_cases.entity_use_cases import (
    CreateEntityUseCase,
    DeactivateEntityUseCase,
    GetEntityChildrenUseCase,
    GetEntityHierarchyUseCase,
    GetEntityUseCase,
    SearchEntitiesUseCase,
    UpdateEntityUseCase,
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
    get_create_entity_uc,
    get_deactivate_entity_uc,
    get_entity_children_uc,
    get_entity_hierarchy_uc,
    get_get_entity_uc,
    get_search_entities_uc,
    get_update_entity_uc,
)
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user
from regulaforge.interfaces.api.v1.schemas import (
    EntityCreateRequest,
    EntityHierarchyResponse,
    EntityListResponse,
    EntityResponse,
    EntityUpdateRequest,
)

router = APIRouter(prefix="/entities", tags=["Entities"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=EntityResponse, status_code=HTTP_201_CREATED)
async def create_entity(
    request: EntityCreateRequest,
    use_case: CreateEntityUseCase = Depends(get_create_entity_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Create a new assessable entity.

    Registers an organization, department, product, system,
    or any entity subject to compliance assessment.
    """
    try:
        entity = await use_case.execute(
            name=request.name,
            entity_type=request.entity_type,
            tenant_id=request.tenant_id,
            description=request.description,
            parent_entity_id=request.parent_entity_id,
            tags=request.tags,
            attributes=request.attributes,
            created_by=current_user.id,
        )
        return _entity_to_response(entity)
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


@router.get("", response_model=EntityListResponse)
async def list_entities(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    tenant_id: Optional[UUID] = Query(default=None, description="Filter by tenant ID"),  # noqa: B008
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    _search: Optional[str] = Query(default=None, description="Full-text _search"),
    sort_by: Optional[str] = Query(default=None, description="Sort field"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order"),
    use_case: SearchEntitiesUseCase = Depends(get_search_entities_uc),  # noqa: B008
) -> Any:
    """List entities with filtering, search, and pagination."""
    filters = {}
    if tenant_id:
        filters["tenant_id"] = tenant_id
    if entity_type:
        filters["entity_type"] = entity_type
    if is_active is not None:
        filters["is_active"] = is_active

    entities, total = await use_case.execute(
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, -(-total // page_size))

    return EntityListResponse(
        items=[_entity_to_response(e) for e in entities],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    use_case: GetEntityUseCase = Depends(get_get_entity_uc),  # noqa: B008
) -> Any:
    """Get an entity by its ID."""
    try:
        entity = await use_case.execute(entity_id)
        return _entity_to_response(entity)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: UUID,
    request: EntityUpdateRequest,
    use_case: UpdateEntityUseCase = Depends(get_update_entity_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Update an existing entity's fields."""
    try:
        updates = request.model_dump(exclude_none=True)
        entity = await use_case.execute(
            entity_id=entity_id,
            updated_by=current_user.id,
            **updates,
        )
        return _entity_to_response(entity)
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


@router.post("/{entity_id}/deactivate", response_model=EntityResponse)
async def deactivate_entity(
    entity_id: UUID,
    use_case: DeactivateEntityUseCase = Depends(get_deactivate_entity_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Deactivate an entity, marking it inactive for assessments."""
    try:
        entity = await use_case.execute(
            entity_id=entity_id,
            deactivate=True,
            by=current_user.id,
        )
        return _entity_to_response(entity)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{entity_id}/activate", response_model=EntityResponse)
async def activate_entity(
    entity_id: UUID,
    use_case: DeactivateEntityUseCase = Depends(get_deactivate_entity_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Reactivate a previously deactivated entity."""
    try:
        entity = await use_case.execute(
            entity_id=entity_id,
            deactivate=False,
            by=current_user.id,
        )
        return _entity_to_response(entity)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{entity_id}/hierarchy", response_model=EntityHierarchyResponse)
async def get_entity_hierarchy(
    entity_id: UUID,
    use_case: GetEntityHierarchyUseCase = Depends(get_entity_hierarchy_uc),  # noqa: B008
) -> Any:
    """Get the parent hierarchy chain for an entity.

    Returns entities from root ancestor to the specified entity.
    """
    try:
        hierarchy = await use_case.execute(entity_id)
        return EntityHierarchyResponse(
            items=[_entity_to_response(e) for e in hierarchy],
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{entity_id}/children", response_model=EntityListResponse)
async def get_entity_children(
    entity_id: UUID,
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    use_case: GetEntityChildrenUseCase = Depends(get_entity_children_uc),  # noqa: B008
) -> Any:
    """Get direct child entities of a parent entity."""
    try:
        children, total = await use_case.execute(
            parent_id=entity_id,
            page=page,
            page_size=page_size,
        )
        total_pages = max(1, -(-total // page_size))
        return EntityListResponse(
            items=[_entity_to_response(c) for c in children],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _entity_to_response(entity: Any) -> dict[str, Any]:
    """Convert an AssessableEntity domain entity to API response."""
    data = entity.to_dict()
    return EntityResponse(
        id=data["id"],
        name=data["name"],
        entity_type=data["entity_type"],
        tenant_id=data["tenant_id"],
        description=data.get("description"),
        parent_entity_id=data.get("parent_entity_id"),
        tags=data.get("tags", []),
        attributes=data.get("attributes", {}),
        is_active=data.get("is_active", True),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )
