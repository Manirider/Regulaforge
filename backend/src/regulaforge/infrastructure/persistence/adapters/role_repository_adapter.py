"""SQLAlchemy-based role repository implementation."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.role import Role, UserRole
from regulaforge.domain.repositories.base import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
)
from regulaforge.domain.repositories.role_repository import RoleRepository
from regulaforge.infrastructure.persistence.models.role_model import RoleModel, UserRoleModel

logger = get_logger(__name__)


class SqlAlchemyRoleRepository(RoleRepository):
    """PostgreSQL-backed role repository using SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entity: Role) -> Role:
        try:
            existing = await self._session.get(RoleModel, entity.id)
            if existing:
                existing.name = entity.name
                existing.description = entity.description
                existing.permissions = entity.permissions
                existing.is_system_role = entity.is_system_role
                existing.updated_by = entity.updated_by
                existing.version = entity.version
            else:
                model = RoleModel(
                    id=entity.id,
                    name=entity.name,
                    description=entity.description,
                    permissions=entity.permissions,
                    is_system_role=entity.is_system_role,
                    created_by=entity.created_by,
                    updated_by=entity.updated_by,
                    version=entity.version,
                )
                self._session.add(model)
            await self._session.flush()
            return entity
        except Exception as e:
            logger.error("Failed to save role %s: %s", entity.id, e)
            raise RepositoryError(f"Failed to save role: {e}", e)

    async def get_by_id(self, entity_id: UUID) -> Optional[Role]:
        try:
            model = await self._session.get(RoleModel, entity_id)
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get role %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to get role: {e}", e)

    async def delete(self, entity_id: UUID) -> None:
        try:
            model = await self._session.get(RoleModel, entity_id)
            if not model:
                raise EntityNotFoundError("Role", entity_id)
            if model.is_system_role:
                raise RepositoryError("Cannot delete system-defined roles")
            await self._session.delete(model)
            await self._session.flush()
        except (EntityNotFoundError, RepositoryError):
            raise
        except Exception as e:
            logger.error("Failed to delete role %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to delete role: {e}", e)

    async def exists(self, entity_id: UUID) -> bool:
        result = await self._session.execute(
            select(RoleModel.id).where(RoleModel.id == entity_id)
        )
        return result.scalar() is not None

    async def get_by_name(self, name: str) -> Optional[Role]:
        try:
            result = await self._session.execute(
                select(RoleModel).where(RoleModel.name == name)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get role by name %s: %s", name, e)
            raise RepositoryError(f"Failed to get role by name: {e}", e)

    async def get_by_permission(self, permission_key: str) -> list[Role]:
        try:
            query = select(RoleModel).where(
                cast(RoleModel.permissions, JSONB).contains([permission_key])
            )
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._to_domain(m) for m in models if m]
        except Exception as e:
            logger.error("Failed to get roles by permission %s: %s", permission_key, e)
            raise RepositoryError(f"Failed to get roles by permission: {e}", e)

    async def get_system_roles(self) -> list[Role]:
        try:
            result = await self._session.execute(
                select(RoleModel).where(RoleModel.is_system_role.is_(True))
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models if m]
        except Exception as e:
            logger.error("Failed to get system roles: %s", e)
            raise RepositoryError(f"Failed to get system roles: {e}", e)

    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        try:
            result = await self._session.execute(
                select(RoleModel)
                .join(UserRoleModel, RoleModel.id == UserRoleModel.role_id)
                .where(UserRoleModel.user_id == user_id)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models if m]
        except Exception as e:
            logger.error("Failed to get user roles for %s: %s", user_id, e)
            raise RepositoryError(f"Failed to get user roles: {e}", e)

    async def assign_role_to_user(
        self, user_id: UUID, role_id: UUID, tenant_id: Optional[UUID] = None
    ) -> UserRole:
        try:
            existing = await self._session.execute(
                select(UserRoleModel).where(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id == role_id,
                    UserRoleModel.tenant_id == tenant_id,
                )
            )
            if existing.scalar_one_or_none():
                raise DuplicateEntityError("UserRole", "user_id/role_id", f"{user_id}/{role_id}")

            assignment = UserRoleModel(
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
            )
            self._session.add(assignment)
            await self._session.flush()

            return UserRole(
                id=assignment.id,
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
            )
        except DuplicateEntityError:
            raise
        except Exception as e:
            logger.error("Failed to assign role %s to user %s: %s", role_id, user_id, e)
            raise RepositoryError(f"Failed to assign role: {e}", e)

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        try:
            result = await self._session.execute(
                select(UserRoleModel).where(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id == role_id,
                )
            )
            model = result.scalar_one_or_none()
            if not model:
                raise EntityNotFoundError("UserRole", f"user={user_id}, role={role_id}")
            await self._session.delete(model)
            await self._session.flush()
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to remove role %s from user %s: %s", role_id, user_id, e)
            raise RepositoryError(f"Failed to remove role: {e}", e)

    async def get_user_permissions(self, user_id: UUID) -> list[str]:
        try:
            result = await self._session.execute(
                select(RoleModel.permissions)
                .join(UserRoleModel, RoleModel.id == UserRoleModel.role_id)
                .where(UserRoleModel.user_id == user_id)
            )
            rows = result.all()
            permissions: list[str] = []
            seen: set = set()
            for (perms,) in rows:
                for p in (perms or []):
                    if p not in seen:
                        permissions.append(p)
                        seen.add(p)
            return permissions
        except Exception as e:
            logger.error("Failed to get permissions for user %s: %s", user_id, e)
            raise RepositoryError(f"Failed to get user permissions: {e}", e)

    async def user_has_permission(self, user_id: UUID, permission: str) -> bool:
        permissions = await self.get_user_permissions(user_id)
        return permission in permissions

    async def user_has_role(self, user_id: UUID, role_name: str) -> bool:
        try:
            result = await self._session.execute(
                select(RoleModel.id)
                .join(UserRoleModel, RoleModel.id == UserRoleModel.role_id)
                .where(
                    UserRoleModel.user_id == user_id,
                    RoleModel.name == role_name,
                )
            )
            return result.scalar() is not None
        except Exception as e:
            logger.error("Failed to check role %s for user %s: %s", role_name, user_id, e)
            raise RepositoryError(f"Failed to check user role: {e}", e)

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Role], int]:
        query = select(RoleModel)

        if filters:
            query = self._apply_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        if sort_by:
            sort_col = getattr(RoleModel, sort_by, None)
            if sort_col:
                order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
                query = query.order_by(order)
        else:
            query = query.order_by(RoleModel.created_at.desc())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        query = select(func.count(RoleModel.id))
        if filters:
            query = self._apply_filters(query, filters)
        result = await self._session.execute(query)
        return result.scalar() or 0

    def _apply_filters(self, query, filters: dict[str, Any]):
        filter_map = {
            "name": RoleModel.name,
            "is_system_role": RoleModel.is_system_role,
        }
        for field, value in filters.items():
            column = filter_map.get(field)
            if column is not None and value is not None:
                query = query.where(column == value)
        return query

    def _to_domain(self, model: RoleModel) -> Role:
        return Role(
            id=model.id,
            name=model.name,
            description=model.description,
            permissions=model.permissions,
            is_system_role=model.is_system_role,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
            version=model.version,
        )
