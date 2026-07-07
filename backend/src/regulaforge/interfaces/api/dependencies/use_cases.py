"""Use case factory dependencies.

Provides factory functions for all application use cases,
wiring their required dependencies via FastAPI's DI.
"""

from fastapi import Depends

from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.use_cases.assessment_use_cases import (
    AddFindingUseCase,
    ApproveAssessmentUseCase,
    CompleteAssessmentUseCase,
    CreateAssessmentUseCase,
    GetAssessmentUseCase,
    ListAssessmentsUseCase,
    StartAssessmentUseCase,
)
from regulaforge.application.use_cases.auth_use_cases import (
    ChangePasswordUseCase,
    LoginUserUseCase,
    RefreshTokenUseCase,
    RegisterUserUseCase,
)
from regulaforge.application.use_cases.document_use_cases import (
    DeleteDocumentUseCase,
    GetDocumentUseCase,
    SearchDocumentsUseCase,
    UploadDocumentUseCase,
    VerifyDocumentUseCase,
)
from regulaforge.application.use_cases.entity_use_cases import (
    CreateEntityUseCase,
    DeactivateEntityUseCase,
    GetEntityChildrenUseCase,
    GetEntityHierarchyUseCase,
    GetEntityUseCase,
    SearchEntitiesUseCase,
    UpdateEntityUseCase,
)
from regulaforge.application.use_cases.regulation_use_cases import (
    AddRequirementUseCase,
    CreateRegulationUseCase,
    GetRegulationUseCase,
    PublishRegulationUseCase,
    SearchRegulationsUseCase,
    UpdateRegulationUseCase,
)
from regulaforge.domain.repositories.assessment_repository import AssessmentRepository
from regulaforge.domain.repositories.document_repository import DocumentRepository
from regulaforge.domain.repositories.entity_repository import EntityRepository
from regulaforge.domain.repositories.regulation_repository import RegulationRepository
from regulaforge.domain.repositories.role_repository import RoleRepository
from regulaforge.domain.repositories.user_repository import UserRepository
from regulaforge.infrastructure.security.adapters.token_service_adapter import (
    JwtTokenAdapter,
    PasswordServiceAdapter,
)
from regulaforge.interfaces.api.dependencies.infrastructure import (
    get_event_publisher,
    get_jwt_service,
    get_password_service,
)
from regulaforge.interfaces.api.dependencies.repositories import (
    get_assessment_repo,
    get_document_repo,
    get_entity_repo,
    get_regulation_repo,
    get_role_repo,
    get_user_repo,
)

# ---------------------------------------------------------------------------
# Regulation use cases
# ---------------------------------------------------------------------------

async def get_create_regulation_uc(
    regulation_repo: RegulationRepository = Depends(get_regulation_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> CreateRegulationUseCase:
    return CreateRegulationUseCase(
        regulation_repo=regulation_repo,
        event_publisher=event_publisher,
    )


async def get_update_regulation_uc(
    regulation_repo: RegulationRepository = Depends(get_regulation_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> UpdateRegulationUseCase:
    return UpdateRegulationUseCase(
        regulation_repo=regulation_repo,
        event_publisher=event_publisher,
    )


async def get_publish_regulation_uc(
    regulation_repo: RegulationRepository = Depends(get_regulation_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> PublishRegulationUseCase:
    return PublishRegulationUseCase(
        regulation_repo=regulation_repo,
        event_publisher=event_publisher,
    )


async def get_get_regulation_uc(
    regulation_repo: RegulationRepository = Depends(get_regulation_repo),
) -> GetRegulationUseCase:
    return GetRegulationUseCase(regulation_repo=regulation_repo)


async def get_search_regulations_uc(
    regulation_repo: RegulationRepository = Depends(get_regulation_repo),
) -> SearchRegulationsUseCase:
    return SearchRegulationsUseCase(regulation_repo=regulation_repo)


async def get_add_requirement_uc(
    regulation_repo: RegulationRepository = Depends(get_regulation_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> AddRequirementUseCase:
    return AddRequirementUseCase(
        regulation_repo=regulation_repo,
        event_publisher=event_publisher,
    )


# ---------------------------------------------------------------------------
# Assessment use cases
# ---------------------------------------------------------------------------

async def get_create_assessment_uc(
    assessment_repo: AssessmentRepository = Depends(get_assessment_repo),
    entity_repo: EntityRepository = Depends(get_entity_repo),
    regulation_repo: RegulationRepository = Depends(get_regulation_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> CreateAssessmentUseCase:
    return CreateAssessmentUseCase(
        assessment_repo=assessment_repo,
        entity_repo=entity_repo,
        regulation_repo=regulation_repo,
        event_publisher=event_publisher,
    )


async def get_start_assessment_uc(
    assessment_repo: AssessmentRepository = Depends(get_assessment_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> StartAssessmentUseCase:
    return StartAssessmentUseCase(
        assessment_repo=assessment_repo,
        event_publisher=event_publisher,
    )


async def get_add_finding_uc(
    assessment_repo: AssessmentRepository = Depends(get_assessment_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> AddFindingUseCase:
    return AddFindingUseCase(
        assessment_repo=assessment_repo,
        event_publisher=event_publisher,
    )


async def get_complete_assessment_uc(
    assessment_repo: AssessmentRepository = Depends(get_assessment_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> CompleteAssessmentUseCase:
    return CompleteAssessmentUseCase(
        assessment_repo=assessment_repo,
        event_publisher=event_publisher,
    )


async def get_approve_assessment_uc(
    assessment_repo: AssessmentRepository = Depends(get_assessment_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> ApproveAssessmentUseCase:
    return ApproveAssessmentUseCase(
        assessment_repo=assessment_repo,
        event_publisher=event_publisher,
    )


async def get_get_assessment_uc(
    assessment_repo: AssessmentRepository = Depends(get_assessment_repo),
) -> GetAssessmentUseCase:
    return GetAssessmentUseCase(assessment_repo=assessment_repo)


async def get_list_assessments_uc(
    assessment_repo: AssessmentRepository = Depends(get_assessment_repo),
) -> ListAssessmentsUseCase:
    return ListAssessmentsUseCase(assessment_repo=assessment_repo)


# ---------------------------------------------------------------------------
# Entity use cases
# ---------------------------------------------------------------------------

async def get_create_entity_uc(
    entity_repo: EntityRepository = Depends(get_entity_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> CreateEntityUseCase:
    return CreateEntityUseCase(
        entity_repo=entity_repo,
        event_publisher=event_publisher,
    )


async def get_get_entity_uc(
    entity_repo: EntityRepository = Depends(get_entity_repo),
) -> GetEntityUseCase:
    return GetEntityUseCase(entity_repo=entity_repo)


async def get_update_entity_uc(
    entity_repo: EntityRepository = Depends(get_entity_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> UpdateEntityUseCase:
    return UpdateEntityUseCase(
        entity_repo=entity_repo,
        event_publisher=event_publisher,
    )


async def get_search_entities_uc(
    entity_repo: EntityRepository = Depends(get_entity_repo),
) -> SearchEntitiesUseCase:
    return SearchEntitiesUseCase(entity_repo=entity_repo)


async def get_entity_hierarchy_uc(
    entity_repo: EntityRepository = Depends(get_entity_repo),
) -> GetEntityHierarchyUseCase:
    return GetEntityHierarchyUseCase(entity_repo=entity_repo)


async def get_entity_children_uc(
    entity_repo: EntityRepository = Depends(get_entity_repo),
) -> GetEntityChildrenUseCase:
    return GetEntityChildrenUseCase(entity_repo=entity_repo)


async def get_deactivate_entity_uc(
    entity_repo: EntityRepository = Depends(get_entity_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> DeactivateEntityUseCase:
    return DeactivateEntityUseCase(
        entity_repo=entity_repo,
        event_publisher=event_publisher,
    )


# ---------------------------------------------------------------------------
# Document use cases
# ---------------------------------------------------------------------------

async def get_upload_document_uc(
    document_repo: DocumentRepository = Depends(get_document_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(
        document_repo=document_repo,
        event_publisher=event_publisher,
    )


async def get_get_document_uc(
    document_repo: DocumentRepository = Depends(get_document_repo),
) -> GetDocumentUseCase:
    return GetDocumentUseCase(document_repo=document_repo)


async def get_verify_document_uc(
    document_repo: DocumentRepository = Depends(get_document_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> VerifyDocumentUseCase:
    return VerifyDocumentUseCase(
        document_repo=document_repo,
        event_publisher=event_publisher,
    )


async def get_search_documents_uc(
    document_repo: DocumentRepository = Depends(get_document_repo),
) -> SearchDocumentsUseCase:
    return SearchDocumentsUseCase(document_repo=document_repo)


async def get_delete_document_uc(
    document_repo: DocumentRepository = Depends(get_document_repo),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(
        document_repo=document_repo,
        event_publisher=event_publisher,
    )


# ---------------------------------------------------------------------------
# Auth use cases (using port abstractions — no infrastructure imports)
# ---------------------------------------------------------------------------

async def get_register_uc(
    user_repo: UserRepository = Depends(get_user_repo),
    role_repo: RoleRepository = Depends(get_role_repo),
) -> RegisterUserUseCase:
    return RegisterUserUseCase(
        user_repo=user_repo,
        role_repo=role_repo,
        password_service=PasswordServiceAdapter(get_password_service()),
    )


async def get_login_uc(
    user_repo: UserRepository = Depends(get_user_repo),
) -> LoginUserUseCase:
    return LoginUserUseCase(
        user_repo=user_repo,
        password_service=PasswordServiceAdapter(get_password_service()),
        jwt_service=JwtTokenAdapter(get_jwt_service()),
    )


async def get_refresh_uc(
    user_repo: UserRepository = Depends(get_user_repo),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        jwt_service=JwtTokenAdapter(get_jwt_service()),
        user_repo=user_repo,
    )


async def get_change_password_uc(
    user_repo: UserRepository = Depends(get_user_repo),
) -> ChangePasswordUseCase:
    return ChangePasswordUseCase(
        user_repo=user_repo,
        password_service=PasswordServiceAdapter(get_password_service()),
    )
