"""SQLAlchemy-based entity repository implementation."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.entity import AssessableEntity
from regulaforge.domain.repositories.base import EntityNotFoundError, RepositoryError
from regulaforge.domain.repositories.entity_repository import EntityRepository
from regulaforge.infrastructure.persistence.models.entity_model import AssessableEntityModel

logger = get_logger(__name__)


class SqlAlchemyEntityRepository(EntityRepository):
    """PostgreSQL-backed entity repository using SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entity: AssessableEntity) -> AssessableEntity:
        try:
            existing = await self._session.get(AssessableEntityModel, entity.id)
            if existing:
                existing.name = entity.name
                existing.description = entity.description
                existing.tags = entity.tags
                existing.attributes = entity.attributes
                existing.is_active = entity.is_active
                existing.updated_by = entity.updated_by
                existing.version = entity.version
            else:
                model = AssessableEntityModel(
                    id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type.value if hasattr(entity.entity_type, 'value') else entity.entity_type,  # noqa: E501
                    tenant_id=entity.tenant_id,
                    description=entity.description,
                    parent_entity_id=entity.parent_entity_id,
                    tags=entity.tags,
                    attributes=entity.attributes,
                    is_active=entity.is_active,
                    created_by=entity.created_by,
                    updated_by=entity.updated_by,
                    version=entity.version,
                )
                self._session.add(model)
            await self._session.flush()
            return entity
        except Exception as e:
            logger.error("Failed to save entity %s: %s", entity.id, e)
            raise RepositoryError(f"Failed to save entity: {e}", e)

    async def get_by_id(self, entity_id: UUID) -> Optional[AssessableEntity]:
        try:
            model = await self._session.get(AssessableEntityModel, entity_id)
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get entity %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to get entity: {e}", e)

    async def delete(self, entity_id: UUID) -> None:
        try:
            model = await self._session.get(AssessableEntityModel, entity_id)
            if not model:
                raise EntityNotFoundError("AssessableEntity", entity_id)
            await self._session.delete(model)
            await self._session.flush()
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to delete entity %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to delete entity: {e}", e)

    async def exists(self, entity_id: UUID) -> bool:
        result = await self._session.execute(
            select(AssessableEntityModel.id).where(AssessableEntityModel.id == entity_id)
        )
        return result.scalar() is not None

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AssessableEntity], int]:
        query = select(AssessableEntityModel)

        if filters:
            query = self._apply_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        if sort_by:
            sort_col = getattr(AssessableEntityModel, sort_by, None)
            if sort_col:
                order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
                query = query.order_by(order)
        else:
            query = query.order_by(AssessableEntityModel.created_at.desc())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        query = select(func.count(AssessableEntityModel.id))
        if filters:
            query = self._apply_filters(query, filters)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_by_tenant(
        self, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[AssessableEntity], int]:
        query = select(AssessableEntityModel).where(
            AssessableEntityModel.tenant_id == tenant_id
        )
        return await self._paginate(query, page, page_size)

    async def get_by_type(
        self, entity_type: str, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[AssessableEntity], int]:
        query = select(AssessableEntityModel).where(
            AssessableEntityModel.entity_type == entity_type,
            AssessableEntityModel.tenant_id == tenant_id,
        )
        return await self._paginate(query, page, page_size)

    async def get_by_name(self, name: str, tenant_id: UUID) -> Optional[AssessableEntity]:
        result = await self._session.execute(
            select(AssessableEntityModel).where(
                AssessableEntityModel.name == name,
                AssessableEntityModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_hierarchy(self, entity_id: UUID) -> list[AssessableEntity]:
        """Traverse parent chain to build hierarchy."""
        hierarchy = []
        current_id = entity_id

        while current_id:
            result = await self._session.execute(
                select(AssessableEntityModel).where(
                    AssessableEntityModel.id == current_id
                )
            )
            model = result.scalar_one_or_none()
            if model:
                hierarchy.insert(0, self._to_domain(model))
                current_id = model.parent_entity_id
            else:
                break

        return hierarchy

    async def get_children(
        self, parent_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[AssessableEntity], int]:
        query = select(AssessableEntityModel).where(
            AssessableEntityModel.parent_entity_id == parent_id
        )
        return await self._paginate(query, page, page_size)

    async def _paginate(
        self, query, page: int, page_size: int
    ) -> tuple[list[AssessableEntity], int]:
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(AssessableEntityModel.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    def _apply_filters(self, query, filters: dict[str, Any]):
        filter_map = {
            "tenant_id": AssessableEntityModel.tenant_id,
            "entity_type": AssessableEntityModel.entity_type,
            "is_active": AssessableEntityModel.is_active,
            "name": AssessableEntityModel.name,
        }
        for field, value in filters.items():
            column = filter_map.get(field)
            if column is not None and value is not None:
                query = query.where(column == value)
        return query

    def _to_domain(self, model: AssessableEntityModel) -> AssessableEntity:
        from regulaforge.config.constants import EntityType

        EntityType(model.entity_type) if hasattr(EntityType, '_value2member_map_') and model.entity_type in EntityType._value2member_map_ else model.entity_type  # noqa: E501

        return AssessableEntity(
            id=model.id,
            name=model.name,
            entity_type=EntityType(model.entity_type),
            tenant_id=model.tenant_id,
            description=model.description,
            parent_entity_id=model.parent_entity_id,
            tags=model.tags,
            attributes=model.attributes,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
            version=model.version,
        )
