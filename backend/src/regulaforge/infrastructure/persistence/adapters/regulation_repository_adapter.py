"""SQLAlchemy-based regulation repository implementation."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.regulation import Regulation, RegulationRequirement
from regulaforge.domain.repositories.base import (
    EntityNotFoundError,
    RepositoryError,
)
from regulaforge.domain.repositories.regulation_repository import RegulationRepository
from regulaforge.infrastructure.persistence.models.regulation_model import (
    RegulationModel,
    RegulationRequirementModel,
)

logger = get_logger(__name__)


class SqlAlchemyRegulationRepository(RegulationRepository):
    """PostgreSQL-backed regulation repository using SQLAlchemy async.

    Maps between domain entities and ORM models, implementing
    all repository interface methods.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entity: Regulation) -> Regulation:
        """Persist a regulation."""
        try:
            existing = await self._session.get(
                RegulationModel, entity.id,
                options=[selectinload(RegulationModel.requirements)],
            )
            if existing:
                await self._update_model(existing, entity)
            else:
                model = self._to_model(entity)
                self._session.add(model)

            await self._session.flush()
            return entity
        except Exception as e:
            logger.error("Failed to save regulation %s: %s", entity.id, e)
            raise RepositoryError(f"Failed to save regulation: {e}", e)

    async def get_by_id(self, entity_id: UUID) -> Optional[Regulation]:
        """Retrieve a regulation by ID."""
        try:
            model = await self._session.get(
                RegulationModel, entity_id,
                options=[selectinload(RegulationModel.requirements)],
            )
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get regulation %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to get regulation: {e}", e)

    async def delete(self, entity_id: UUID) -> None:
        """Delete a regulation."""
        try:
            model = await self._session.get(RegulationModel, entity_id)
            if not model:
                raise EntityNotFoundError("Regulation", entity_id)
            await self._session.delete(model)
            await self._session.flush()
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to delete regulation %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to delete regulation: {e}", e)

    async def exists(self, entity_id: UUID) -> bool:
        """Check if a regulation exists."""
        result = await self._session.execute(
            select(RegulationModel.id).where(RegulationModel.id == entity_id)
        )
        return result.scalar() is not None

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Regulation], int]:
        """Search regulations with filtering and pagination."""
        query = select(RegulationModel)

        if filters:
            query = self._apply_filters(query, filters)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        # Sorting
        if sort_by:
            sort_col = getattr(RegulationModel, sort_by, None)
            if sort_col:
                order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
                query = query.order_by(order)
        else:
            query = query.order_by(RegulationModel.created_at.desc())

        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        query = query.options(selectinload(RegulationModel.requirements))

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]

        return domains, total

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        """Count regulations matching filters."""
        query = select(func.count(RegulationModel.id))
        if filters:
            query = self._apply_filters(query, filters)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_by_code(self, code: str) -> Optional[Regulation]:
        """Find regulation by unique code."""
        result = await self._session.execute(
            select(RegulationModel)
            .where(RegulationModel.code == code)
            .options(selectinload(RegulationModel.requirements))
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_active_by_category(
        self, category: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Regulation], int]:
        """Get active regulations by category."""
        query = select(RegulationModel).where(
            RegulationModel.category == category,
            RegulationModel.status == "active",
        )
        return await self._paginate(query, page, page_size)

    async def get_by_jurisdiction(
        self, jurisdiction: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Regulation], int]:
        """Get regulations by jurisdiction."""
        query = select(RegulationModel).where(
            RegulationModel.jurisdiction == jurisdiction
        )
        return await self._paginate(query, page, page_size)

    async def get_all_active(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Regulation], int]:
        """Get all active regulations."""
        query = select(RegulationModel).where(
            RegulationModel.status == "active"
        )
        return await self._paginate(query, page, page_size)

    async def search_by_text(
        self, query_str: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Regulation], int]:
        """Full-text search on title, code, description."""
        search_filter = or_(
            RegulationModel.title.ilike(f"%{query_str}%"),
            RegulationModel.code.ilike(f"%{query_str}%"),
            RegulationModel.description.ilike(f"%{query_str}%"),
        )
        query = select(RegulationModel).where(search_filter)
        return await self._paginate(query, page, page_size)

    async def get_version_history(self, regulation_id: UUID) -> list[dict]:
        """Get version history (simplified - extend with version table)."""
        results = await self._session.execute(
            select(RegulationModel)
            .where(
                or_(
                    RegulationModel.id == regulation_id,
                    RegulationModel.superseded_by_id == regulation_id,
                    RegulationModel.parent_regulation_id == regulation_id,
                )
            )
            .order_by(RegulationModel.created_at)
        )
        models = results.scalars().all()
        return [{"id": str(m.id), "version": m.version_str, "status": m.status, "created_at": m.created_at.isoformat()} for m in models]  # noqa: E501

    async def bulk_save(self, regulations: list[Regulation]) -> list[Regulation]:
        """Bulk persist regulations."""
        saved = []
        for reg in regulations:
            saved.append(await self.save(reg))
        return saved

    async def _paginate(
        self, query: Select, page: int, page_size: int
    ) -> tuple[list[Regulation], int]:
        """Apply pagination and return domain entities."""
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(RegulationModel.created_at.desc())
        query = query.offset(offset).limit(page_size)
        query = query.options(selectinload(RegulationModel.requirements))

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    def _apply_filters(self, query: Select, filters: dict[str, Any]) -> Select:
        """Apply dynamic filters to query."""
        filter_map = {
            "status": RegulationModel.status,
            "category": RegulationModel.category,
            "jurisdiction": RegulationModel.jurisdiction,
            "issuing_body": RegulationModel.issuing_body,
            "code": RegulationModel.code,
        }
        for field, value in filters.items():
            column = filter_map.get(field)
            if column is not None and value is not None:
                query = query.where(column.in_(value)) if isinstance(value, list) else query.where(column == value)
        return query

    def _to_model(self, entity: Regulation) -> RegulationModel:
        """Convert domain entity to ORM model."""
        return RegulationModel(
            id=entity.id,
            title=entity.title,
            code=entity.code,
            description=entity.description,
            category=entity.category.value if hasattr(entity.category, 'value') else entity.category,
            jurisdiction=entity.jurisdiction.value if hasattr(entity.jurisdiction, 'value') else entity.jurisdiction,
            issuing_body=entity.issuing_body,
            effective_date=entity.effective_date,
            status=entity.status.value if hasattr(entity.status, 'value') else entity.status,
            version_str=entity.version_str,
            tags=entity.tags,
            parent_regulation_id=entity.parent_regulation_id,
            superseded_by_id=entity.superseded_by_id,
            extra_metadata=entity.metadata,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            version=entity.version,
            requirements=[
                RegulationRequirementModel(
                    id=uuid4(),
                    regulation_id=entity.id,
                    code=r.code,
                    title=r.title,
                    description=r.description,
                    parent_requirement_id=None,
                    is_mandatory=r.is_mandatory,
                    risk_weight=r.risk_weight,
                    guidance=r.guidance,
                    references=r.references,
                    order_index=idx,
                )
                for idx, r in enumerate(entity.requirements)
            ],
        )

    async def _update_model(self, model: RegulationModel, entity: Regulation) -> None:
        """Update an existing ORM model from a domain entity."""
        model.title = entity.title
        model.code = entity.code
        model.description = entity.description
        model.category = entity.category.value if hasattr(entity.category, 'value') else entity.category
        model.jurisdiction = entity.jurisdiction.value if hasattr(entity.jurisdiction, 'value') else entity.jurisdiction
        model.issuing_body = entity.issuing_body
        model.effective_date = entity.effective_date
        model.status = entity.status.value if hasattr(entity.status, 'value') else entity.status
        model.version_str = entity.version_str
        model.tags = entity.tags
        model.parent_regulation_id = entity.parent_regulation_id
        model.superseded_by_id = entity.superseded_by_id
        model.extra_metadata = entity.metadata
        model.updated_by = entity.updated_by
        # Delete existing requirements and recreate
        model.requirements.clear()
        for idx, r in enumerate(entity.requirements):
            model.requirements.append(RegulationRequirementModel(
                id=uuid4(),
                regulation_id=entity.id,
                code=r.code,
                title=r.title,
                description=r.description,
                parent_requirement_id=None,
                is_mandatory=r.is_mandatory,
                risk_weight=r.risk_weight,
                guidance=r.guidance,
                references=r.references,
                order_index=idx,
            ))

    def _to_domain(self, model: RegulationModel) -> Regulation:
        """Convert ORM model to domain entity."""
        # Import enums from constants
        from regulaforge.config.constants import RegulationCategory, RegulationJurisdiction, RegulationStatus

        # Parse category and jurisdiction
        category = self._parse_enum(model.category, RegulationCategory)
        jurisdiction = self._parse_enum(model.jurisdiction, RegulationJurisdiction)
        status = self._parse_enum(model.status, RegulationStatus)

        regulation = Regulation(
            id=model.id,
            title=model.title,
            code=model.code,
            description=model.description,
            category=category,
            jurisdiction=jurisdiction,
            issuing_body=model.issuing_body,
            effective_date=model.effective_date,
            status=status,
            version=model.version_str,
            tags=model.tags,
            parent_regulation_id=model.parent_regulation_id,
            superseded_by_id=model.superseded_by_id,
            metadata=model.extra_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
        )

        # Add requirements
        if hasattr(model, 'requirements') and model.requirements:
            for req_model in model.requirements:
                regulation.add_requirement(RegulationRequirement(
                    code=req_model.code,
                    title=req_model.title,
                    description=req_model.description,
                    parent_requirement_code=None,
                    is_mandatory=req_model.is_mandatory,
                    risk_weight=req_model.risk_weight,
                    guidance=req_model.guidance,
                    references=req_model.references,
                ))

        return regulation

    @staticmethod
    def _parse_enum(value: str, enum_class: type) -> Any:
        """Parse a string value into an enum member."""
        try:
            return enum_class(value)
        except (ValueError, KeyError):
            # Return the raw value for forward-compatibility
            return value


from uuid import uuid4  # noqa: E402
