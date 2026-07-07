"""Compliance assessment API endpoints.

Manages the assessment lifecycle: creation, execution,
review, approval, and finding tracking.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from regulaforge.application.use_cases.assessment_use_cases import (
    AddFindingUseCase,
    ApproveAssessmentUseCase,
    CompleteAssessmentUseCase,
    CreateAssessmentUseCase,
    GetAssessmentUseCase,
    ListAssessmentsUseCase,
    StartAssessmentUseCase,
)
from regulaforge.config.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    MAX_PAGE_SIZE,
)
from regulaforge.domain.entities.user import User
from regulaforge.domain.repositories.base import EntityNotFoundError
from regulaforge.interfaces.api.dependencies import (
    get_add_finding_uc,
    get_approve_assessment_uc,
    get_complete_assessment_uc,
    get_create_assessment_uc,
    get_get_assessment_uc,
    get_list_assessments_uc,
    get_start_assessment_uc,
)
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user
from regulaforge.interfaces.api.v1.schemas import (
    AssessmentCompleteRequest,
    AssessmentCreateRequest,
    AssessmentListResponse,
    AssessmentResponse,
    FindingCreateRequest,
)

router = APIRouter(prefix="/assessments", tags=["Assessments"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=AssessmentResponse, status_code=HTTP_201_CREATED)
async def create_assessment(
    request: AssessmentCreateRequest,
    use_case: CreateAssessmentUseCase = Depends(get_create_assessment_uc),  # noqa: B008
) -> Any:
    """Create a new compliance assessment.

    Schedules an assessment of a specific entity against
    one or more regulations.
    """
    try:
        assessment = await use_case.execute(
            title=request.title,
            entity_id=request.entity_id,
            regulation_ids=request.regulation_ids,
            assessor_id=request.assessor_id,
            due_date=request.due_date,
            scope_description=request.scope_description,
            created_by=request.assessor_id,
            metadata=request.metadata,
        )
        return _assessment_to_response(assessment)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=AssessmentListResponse)
async def list_assessments(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    entity_id: Optional[UUID] = Query(default=None, description="Filter by entity"),  # noqa: B008
    sort_by: Optional[str] = Query(default=None, description="Sort field"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order"),
    use_case: ListAssessmentsUseCase = Depends(get_list_assessments_uc),  # noqa: B008
) -> Any:
    """List compliance assessments with filtering and pagination."""
    filters = {}
    if status:
        filters["status"] = status
    if entity_id:
        filters["entity_id"] = entity_id

    assessments, total = await use_case.execute(
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, -(-total // page_size))

    return AssessmentListResponse(
        items=[_assessment_to_response(a) for a in assessments],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: UUID,
    use_case: GetAssessmentUseCase = Depends(get_get_assessment_uc),  # noqa: B008
) -> Any:
    """Get a compliance assessment by ID."""
    try:
        assessment = await use_case.execute(assessment_id)
        return _assessment_to_response(assessment)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{assessment_id}/start", response_model=AssessmentResponse)
async def start_assessment(
    assessment_id: UUID,
    use_case: StartAssessmentUseCase = Depends(get_start_assessment_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Start a scheduled assessment."""
    try:
        assessment = await use_case.execute(
            assessment_id=assessment_id,
            started_by=current_user.id,
        )
        return _assessment_to_response(assessment)
    except (EntityNotFoundError, ValueError) as e:
        status_code = HTTP_404_NOT_FOUND if isinstance(e, EntityNotFoundError) else HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/{assessment_id}/findings", response_model=AssessmentResponse)
async def add_finding(
    assessment_id: UUID,
    request: FindingCreateRequest,
    use_case: AddFindingUseCase = Depends(get_add_finding_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Add a compliance finding to an assessment."""
    try:
        assessment = await use_case.execute(
            assessment_id=assessment_id,
            requirement_code=request.requirement_code,
            title=request.title,
            description=request.description,
            risk_level=request.risk_level,
            impact_score=request.impact_score,
            likelihood_score=request.likelihood_score,
            remediation_recommendation=request.remediation_recommendation,
            assigned_to=request.assigned_to,
            added_by=current_user.id,
        )
        return _assessment_to_response(assessment)
    except (EntityNotFoundError, ValueError) as e:
        status_code = HTTP_404_NOT_FOUND if isinstance(e, EntityNotFoundError) else HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/{assessment_id}/complete", response_model=AssessmentResponse)
async def complete_assessment(
    assessment_id: UUID,
    request: AssessmentCompleteRequest,
    use_case: CompleteAssessmentUseCase = Depends(get_complete_assessment_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Complete an assessment with a final score."""
    try:
        assessment = await use_case.execute(
            assessment_id=assessment_id,
            score=request.score,
            completed_by=current_user.id,
        )
        return _assessment_to_response(assessment)
    except (EntityNotFoundError, ValueError) as e:
        status_code = HTTP_404_NOT_FOUND if isinstance(e, EntityNotFoundError) else HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/{assessment_id}/approve", response_model=AssessmentResponse)
async def approve_assessment(
    assessment_id: UUID,
    use_case: ApproveAssessmentUseCase = Depends(get_approve_assessment_uc),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Any:
    """Approve a completed assessment."""
    try:
        assessment = await use_case.execute(
            assessment_id=assessment_id,
            reviewer_id=current_user.id,
        )
        return _assessment_to_response(assessment)
    except (EntityNotFoundError, ValueError) as e:
        status_code = HTTP_404_NOT_FOUND if isinstance(e, EntityNotFoundError) else HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _assessment_to_response(assessment: Any) -> dict[str, Any]:
    """Convert a ComplianceAssessment domain entity to API response."""
    data = assessment.to_dict()
    return AssessmentResponse(
        id=data["id"],
        title=data["title"],
        entity_id=data["entity_id"],
        entity_type=data["entity_type"],
        regulation_ids=data["regulation_ids"],
        assessor_id=data["assessor_id"],
        due_date=data["due_date"],
        status=data["status"],
        scope_description=data.get("scope_description"),
        findings=data.get("findings", []),
        overall_score=data.get("overall_score"),
        compliance_level=data.get("compliance_level"),
        approved_by=data.get("approved_by"),
        approved_at=data.get("approved_at"),
        completed_at=data.get("completed_at"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )
