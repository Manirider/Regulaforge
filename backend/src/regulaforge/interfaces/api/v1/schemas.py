from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from regulaforge.config.constants import (
    EntityType,
    RegulationCategory,
    RegulationJurisdiction,
    RiskLevel,
)


class RegisterRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    username: str = Field(..., min_length=3, max_length=150, examples=["johndoe"])
    password: str = Field(..., min_length=12, max_length=128)
    full_name: Optional[str] = Field(None, examples=["John Doe"])
    tenant_id: Optional[UUID] = Field(None)


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(...)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(...)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(...)
    new_password: str = Field(..., min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_domain(cls, user) -> UserResponse:
        data = user.to_dict()
        return cls(
            id=str(data.get("id", "")),
            email=data.get("email", ""),
            username=getattr(user, "username", ""),
            full_name=data.get("full_name"),
            tenant_id=str(data["tenant_id"]) if data.get("tenant_id") else None,
            is_active=data.get("is_active", True),
            is_superuser=data.get("is_superuser", False),
            last_login_at=data.get("last_login_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    permissions: list[str] = []
    is_system_role: bool = False

    @classmethod
    def from_domain(cls, role) -> RoleResponse:
        data = role.to_dict()
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description"),
            permissions=data.get("permissions", []),
            is_system_role=data.get("is_system_role", False),
        )


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Regulation schemas
# ---------------------------------------------------------------------------


class RegulationCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=500, description="Regulation title")
    code: str = Field(..., min_length=2, max_length=50, description="Unique regulation code")
    description: str = Field(..., min_length=1, description="Detailed description")
    category: RegulationCategory = Field(..., description="Regulation category")
    jurisdiction: RegulationJurisdiction = Field(..., description="Applicable jurisdiction")
    issuing_body: str = Field(..., min_length=1, max_length=200, description="Regulatory body")
    effective_date: date = Field(..., description="Effective date")
    tags: Optional[list[str]] = Field(default=None, description="Searchable tags")
    parent_regulation_id: Optional[UUID] = Field(default=None, description="Parent regulation ID")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Flexible metadata")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Code cannot be empty")
        return v.upper().strip()


class RegulationResponse(BaseModel):
    id: UUID
    title: str
    code: str
    description: str
    category: str
    jurisdiction: str
    issuing_body: str
    effective_date: str
    status: str
    version: str
    tags: list[str]
    parent_regulation_id: Optional[UUID] = None
    superseded_by_id: Optional[UUID] = None
    requirements: list[dict[str, Any]] = []
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class RegulationListResponse(BaseModel):
    items: list[RegulationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RegulationUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=500)
    description: Optional[str] = None
    category: Optional[RegulationCategory] = None
    jurisdiction: Optional[RegulationJurisdiction] = None
    issuing_body: Optional[str] = None
    effective_date: Optional[date] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class RequirementCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100, description="Requirement code")
    title: str = Field(..., min_length=3, max_length=500, description="Requirement title")
    description: str = Field(..., description="Requirement description")
    is_mandatory: bool = Field(default=True, description="Whether requirement is mandatory")
    risk_weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Risk weight")
    guidance: Optional[str] = Field(default=None, description="Implementation guidance")
    references: Optional[list[str]] = Field(default=None, description="Reference links")
    parent_requirement_code: Optional[str] = Field(default=None, description="Parent requirement code")


# ---------------------------------------------------------------------------
# Assessment schemas
# ---------------------------------------------------------------------------


class AssessmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=500, description="Assessment title")
    entity_id: UUID = Field(..., description="ID of entity to assess")
    regulation_ids: list[UUID] = Field(..., min_length=1, description="Regulations to assess against")
    assessor_id: UUID = Field(..., description="Assessor user ID")
    due_date: date = Field(..., description="Assessment due date")
    scope_description: Optional[str] = Field(default=None, description="Assessment scope")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Flexible metadata")


class FindingCreateRequest(BaseModel):
    requirement_code: str = Field(..., description="Related requirement code")
    title: str = Field(..., min_length=3, max_length=500, description="Finding title")
    description: str = Field(..., description="Detailed description")
    risk_level: RiskLevel = Field(..., description="Risk severity")
    impact_score: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Impact score")
    likelihood_score: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Likelihood score")
    remediation_recommendation: Optional[str] = Field(default=None, description="Suggested fix")
    assigned_to: Optional[UUID] = Field(default=None, description="Assignee for remediation")


class AssessmentCompleteRequest(BaseModel):
    score: float = Field(..., ge=0.0, le=100.0, description="Final compliance score (0-100)")


class AssessmentResponse(BaseModel):
    id: UUID
    title: str
    entity_id: UUID
    entity_type: str
    regulation_ids: list[UUID]
    assessor_id: UUID
    due_date: str
    status: str
    scope_description: Optional[str] = None
    findings: list[dict[str, Any]] = []
    overall_score: Optional[float] = None
    compliance_level: Optional[str] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class AssessmentListResponse(BaseModel):
    items: list[AssessmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Entity schemas
# ---------------------------------------------------------------------------


class EntityCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    tenant_id: UUID = Field(..., description="Tenant this entity belongs to")
    description: Optional[str] = Field(default=None, description="Detailed description")
    parent_entity_id: Optional[UUID] = Field(default=None, description="Parent entity ID")
    tags: Optional[list[str]] = Field(default=None, description="Searchable tags")
    attributes: Optional[dict[str, Any]] = Field(default=None, description="Flexible attributes")


class EntityResponse(BaseModel):
    id: UUID
    name: str
    entity_type: str
    tenant_id: str
    description: Optional[str] = None
    parent_entity_id: Optional[UUID] = None
    tags: list[str] = []
    attributes: dict[str, Any] = {}
    is_active: bool = True
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class EntityListResponse(BaseModel):
    items: list[EntityResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EntityUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    attributes: Optional[dict[str, Any]] = None
    parent_entity_id: Optional[UUID] = None


class EntityHierarchyResponse(BaseModel):
    items: list[EntityResponse]


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    file_name: str
    file_path: str
    mime_type: str
    file_size_bytes: int
    artifact_type: str
    tenant_id: str
    uploaded_by: str
    description: Optional[str] = None
    tags: list[str] = []
    checksum: Optional[str] = None
    is_verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    processing_status: str = "pending"
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentVerifyRequest(BaseModel):
    verified_by: UUID = Field(..., description="User ID verifying the document")
