"""SQLAlchemy-based assessment repository implementation."""

from datetime import date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.compliance_assessment import ComplianceAssessment
from regulaforge.domain.repositories.assessment_repository import AssessmentRepository
from regulaforge.domain.repositories.base import EntityNotFoundError, RepositoryError
from regulaforge.infrastructure.persistence.models.assessment_model import (
    AssessmentRegulationModel,
    ComplianceAssessmentModel,
)

logger = get_logger(__name__)


class SqlAlchemyAssessmentRepository(AssessmentRepository):
    """PostgreSQL-backed assessment repository using SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entity: ComplianceAssessment) -> ComplianceAssessment:
        try:
            existing = await self._session.get(
                ComplianceAssessmentModel, entity.id,
                options=[selectinload(ComplianceAssessmentModel.regulation_links)],
            )
            if existing:
                await self._update_model(existing, entity)
            else:
                model = self._to_model(entity)
                self._session.add(model)
            await self._session.flush()
            return entity
        except Exception as e:
            logger.error("Failed to save assessment %s: %s", entity.id, e)
            raise RepositoryError(f"Failed to save assessment: {e}", e)

    async def get_by_id(self, entity_id: UUID) -> Optional[ComplianceAssessment]:
        try:
            model = await self._session.get(
                ComplianceAssessmentModel, entity_id,
                options=[
                    selectinload(ComplianceAssessmentModel.findings),
                    selectinload(ComplianceAssessmentModel.regulation_links),
                ],
            )
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get assessment %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to get assessment: {e}", e)

    async def delete(self, entity_id: UUID) -> None:
        try:
            model = await self._session.get(ComplianceAssessmentModel, entity_id)
            if not model:
                raise EntityNotFoundError("ComplianceAssessment", entity_id)
            await self._session.delete(model)
            await self._session.flush()
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to delete assessment %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to delete assessment: {e}", e)

    async def exists(self, entity_id: UUID) -> bool:
        result = await self._session.execute(
            select(ComplianceAssessmentModel.id).where(
                ComplianceAssessmentModel.id == entity_id
            )
        )
        return result.scalar() is not None

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ComplianceAssessment], int]:
        query = select(ComplianceAssessmentModel)

        if filters:
            query = self._apply_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        if sort_by:
            sort_col = getattr(ComplianceAssessmentModel, sort_by, None)
            if sort_col:
                order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
                query = query.order_by(order)
        else:
            query = query.order_by(ComplianceAssessmentModel.updated_at.desc())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        query = query.options(
            selectinload(ComplianceAssessmentModel.findings),
            selectinload(ComplianceAssessmentModel.regulation_links),
        )

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        query = select(func.count(ComplianceAssessmentModel.id))
        if filters:
            query = self._apply_filters(query, filters)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_by_entity(
        self, entity_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        query = select(ComplianceAssessmentModel).where(
            ComplianceAssessmentModel.entity_id == entity_id
        )
        return await self._paginate(query, page, page_size)

    async def get_by_regulation(
        self, regulation_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        query = select(ComplianceAssessmentModel).join(
            AssessmentRegulationModel
        ).where(
            AssessmentRegulationModel.regulation_id == regulation_id
        )
        return await self._paginate(query, page, page_size)

    async def get_by_assignee(
        self, assignee_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        query = select(ComplianceAssessmentModel).where(
            ComplianceAssessmentModel.assessor_id == assignee_id
        )
        return await self._paginate(query, page, page_size)

    async def get_by_status(
        self, status: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        query = select(ComplianceAssessmentModel).where(
            ComplianceAssessmentModel.status == status
        )
        return await self._paginate(query, page, page_size)

    async def get_overdue(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[ComplianceAssessment], int]:
        today = date.today()
        query = select(ComplianceAssessmentModel).where(
            ComplianceAssessmentModel.due_date < today,
            ComplianceAssessmentModel.status.notin_(["completed", "cancelled"]),
        )
        return await self._paginate(query, page, page_size)

    async def get_compliance_summary(self, entity_id: UUID) -> dict:
        """Get compliance summary metrics for an entity."""
        # Get all assessments for entity
        assessments, _ = await self.get_by_entity(entity_id, page=1, page_size=100)

        total = len(assessments)
        completed = sum(1 for a in assessments if a.status.value == "completed")
        in_progress = sum(1 for a in assessments if a.status.value == "in_progress")
        overdue = sum(
            1 for a in assessments
            if a.due_date < date.today() and a.status.value not in ("completed", "cancelled")
        )

        scores = [a.overall_score for a in assessments if a.overall_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "entity_id": str(entity_id),
            "total_assessments": total,
            "completed": completed,
            "in_progress": in_progress,
            "overdue": overdue,
            "average_score": round(avg_score, 2),
            "compliance_rate": round(
                sum(1 for s in scores if s >= 80) / len(scores) * 100 if scores else 0, 1
            ),
        }

    async def _paginate(self, query, page: int, page_size: int) -> tuple[list[ComplianceAssessment], int]:
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(ComplianceAssessmentModel.updated_at.desc())
        query = query.offset(offset).limit(page_size)
        query = query.options(
            selectinload(ComplianceAssessmentModel.findings),
            selectinload(ComplianceAssessmentModel.regulation_links),
        )

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    def _apply_filters(self, query, filters: dict[str, Any]):
        filter_map = {
            "status": ComplianceAssessmentModel.status,
            "entity_id": ComplianceAssessmentModel.entity_id,
            "entity_type": ComplianceAssessmentModel.entity_type,
            "assessor_id": ComplianceAssessmentModel.assessor_id,
        }
        for field, value in filters.items():
            column = filter_map.get(field)
            if column is not None and value is not None:
                query = query.where(column.in_(value)) if isinstance(value, list) else query.where(column == value)
        return query

    def _to_model(self, entity: ComplianceAssessment) -> ComplianceAssessmentModel:
        return ComplianceAssessmentModel(
            id=entity.id,
            title=entity.title,
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            assessor_id=entity.assessor_id,
            due_date=entity.due_date,
            status=entity.status.value if hasattr(entity.status, 'value') else entity.status,
            scope_description=entity.scope_description,
            overall_score=entity.overall_score,
            approved_by=entity.approved_by,
            approved_at=entity.approved_at,
            completed_at=entity.completed_at,
            extra_metadata=entity._metadata if hasattr(entity, '_metadata') else {},
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            version=entity.version,
            regulation_links=[
                AssessmentRegulationModel(
                    assessment_id=entity.id,
                    regulation_id=rid,
                )
                for rid in (entity.regulation_ids or [])
            ],
        )

    def _to_domain(self, model: ComplianceAssessmentModel) -> ComplianceAssessment:
        from regulaforge.config.constants import AssessmentStatus

        status = AssessmentStatus(model.status)

        assessment = ComplianceAssessment(
            id=model.id,
            title=model.title,
            entity_id=model.entity_id,
            entity_type=model.entity_type,
            regulation_ids=[lr.regulation_id for lr in (model.regulation_links or [])],
            assessor_id=model.assessor_id,
            due_date=model.due_date,
            status=status,
            scope_description=model.scope_description,
            metadata=model.extra_metadata if hasattr(model, 'extra_metadata') else {},
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
            version=model.version,
        )

        # Restore persisted state that is not set via constructor
        assessment._overall_score = model.overall_score
        assessment._completed_at = model.completed_at
        assessment._approved_by = model.approved_by
        assessment._approved_at = model.approved_at

        return assessment

    async def _update_model(self, model: ComplianceAssessmentModel, entity: ComplianceAssessment) -> None:
        """Update existing model from domain entity."""
        model.title = entity.title
        model.entity_id = entity.entity_id
        model.entity_type = entity.entity_type
        model.assessor_id = entity.assessor_id
        model.due_date = entity.due_date
        model.status = entity.status.value if hasattr(entity.status, 'value') else entity.status
        model.scope_description = entity.scope_description
        model.overall_score = entity.overall_score
        model.approved_by = entity.approved_by
        model.approved_at = entity.approved_at
        model.completed_at = entity.completed_at
        if hasattr(entity, '_metadata'):
            model.extra_metadata = entity._metadata
        model.updated_by = entity.updated_by
        model.version = entity.version
        # Sync regulation links
        existing_ids = {lr.regulation_id for lr in (model.regulation_links or [])}
        new_ids = set(entity.regulation_ids or [])
        for lr in list(model.regulation_links or []):
            if lr.regulation_id not in new_ids:
                model.regulation_links.remove(lr)
        for rid in new_ids:
            if rid not in existing_ids:
                model.regulation_links.append(AssessmentRegulationModel(
                    assessment_id=entity.id,
                    regulation_id=rid,
                ))
