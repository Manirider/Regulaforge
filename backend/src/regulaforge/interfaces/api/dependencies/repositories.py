"""Repository adapter dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.domain.repositories.assessment_repository import AssessmentRepository
from regulaforge.domain.repositories.document_repository import DocumentRepository
from regulaforge.domain.repositories.entity_repository import EntityRepository
from regulaforge.domain.repositories.regulation_repository import RegulationRepository
from regulaforge.domain.repositories.role_repository import RoleRepository
from regulaforge.domain.repositories.user_repository import UserRepository
from regulaforge.infrastructure.persistence.adapters.assessment_repository_adapter import (
    SqlAlchemyAssessmentRepository,
)
from regulaforge.infrastructure.persistence.adapters.document_repository_adapter import (
    SqlAlchemyDocumentRepository,
)
from regulaforge.infrastructure.persistence.adapters.entity_repository_adapter import (
    SqlAlchemyEntityRepository,
)
from regulaforge.infrastructure.persistence.adapters.regulation_repository_adapter import (
    SqlAlchemyRegulationRepository,
)
from regulaforge.infrastructure.persistence.adapters.role_repository_adapter import (
    SqlAlchemyRoleRepository,
)
from regulaforge.infrastructure.persistence.adapters.user_repository_adapter import (
    SqlAlchemyUserRepository,
)
from regulaforge.interfaces.api.dependencies.database import get_db_session


async def get_regulation_repo(
    session: AsyncSession = Depends(get_db_session),
) -> RegulationRepository:
    return SqlAlchemyRegulationRepository(session)


async def get_assessment_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AssessmentRepository:
    return SqlAlchemyAssessmentRepository(session)


async def get_entity_repo(
    session: AsyncSession = Depends(get_db_session),
) -> EntityRepository:
    return SqlAlchemyEntityRepository(session)


async def get_document_repo(
    session: AsyncSession = Depends(get_db_session),
) -> DocumentRepository:
    return SqlAlchemyDocumentRepository(session)


async def get_user_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return SqlAlchemyUserRepository(session)


async def get_role_repo(
    session: AsyncSession = Depends(get_db_session),
) -> RoleRepository:
    return SqlAlchemyRoleRepository(session)
