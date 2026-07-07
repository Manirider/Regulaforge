"""SQLAlchemy-based user repository implementation."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.user import User
from regulaforge.domain.repositories.base import (
    EntityNotFoundError,
    RepositoryError,
)
from regulaforge.domain.repositories.user_repository import UserRepository
from regulaforge.infrastructure.persistence.models.user_model import UserModel
from regulaforge.infrastructure.security.password_service import PasswordService

logger = get_logger(__name__)


class SqlAlchemyUserRepository(UserRepository):
    """PostgreSQL-backed user repository using SQLAlchemy async.

    Maps between User domain entity and UserModel ORM model,
    implementing all UserRepository interface methods.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entity: User) -> User:
        """Persist a new or updated user."""
        try:
            existing = await self._session.get(UserModel, entity.id)
            if existing:
                self._update_model(existing, entity)
            else:
                model = self._to_model(entity)
                self._session.add(model)

            await self._session.flush()
            return entity
        except Exception as e:
            logger.error("Failed to save user %s: %s", entity.id, e)
            raise RepositoryError(f"Failed to save user: {e}", e)

    async def get_by_id(self, entity_id: UUID) -> Optional[User]:
        """Retrieve a user by ID with roles eagerly loaded."""
        try:
            result = await self._session.execute(
                select(UserModel)
                .where(UserModel.id == entity_id)
                .options(joinedload(UserModel.roles))
            )
            model = result.unique().scalar_one_or_none()
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get user %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to get user: {e}", e)

    async def delete(self, entity_id: UUID) -> None:
        """Delete a user."""
        try:
            model = await self._session.get(UserModel, entity_id)
            if not model:
                raise EntityNotFoundError("User", entity_id)
            await self._session.delete(model)
            await self._session.flush()
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to delete user %s: %s", entity_id, e)
            raise RepositoryError(f"Failed to delete user: {e}", e)

    async def exists(self, entity_id: UUID) -> bool:
        """Check if a user exists."""
        result = await self._session.execute(
            select(UserModel.id).where(UserModel.id == entity_id)
        )
        return result.scalar() is not None

    async def get_by_email(self, email: str) -> Optional[User]:
        """Find a user by email."""
        try:
            result = await self._session.execute(
                select(UserModel)
                .where(UserModel.email == email)
                .options(joinedload(UserModel.roles))
            )
            model = result.unique().scalar_one_or_none()
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get user by email %s: %s", email, e)
            raise RepositoryError(f"Failed to get user by email: {e}", e)

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and plain-text password.

        Args:
            email: The user's email address.
            password: The plain-text password to verify.

        Returns:
            The authenticated User if credentials match, None otherwise.
        """
        try:
            user = await self.get_by_email(email)
            if user is None or user.password_hash is None:
                return None

            password_service = PasswordService()
            if not password_service.verify_password(password, user.password_hash):
                return None

            return user
        except Exception as e:
            logger.error("Failed to authenticate user %s: %s", email, e)
            raise RepositoryError(f"Failed to authenticate user: {e}", e)

    async def get_by_username(self, username: str) -> Optional[User]:
        """Find a user by username."""
        try:
            result = await self._session.execute(
                select(UserModel)
                .where(UserModel.username == username)
                .options(joinedload(UserModel.roles))
            )
            model = result.unique().scalar_one_or_none()
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get user by username %s: %s", username, e)
            raise RepositoryError(f"Failed to get user by username: {e}", e)

    async def get_by_tenant(
        self, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[User], int]:
        """Get users belonging to a tenant with pagination."""
        query = select(UserModel).where(UserModel.tenant_id == tenant_id)
        return await self._paginate(query, page, page_size)

    async def get_active_users(self, page: int = 1, page_size: int = 20) -> tuple[list[User], int]:
        """Get all active users with pagination."""
        query = select(UserModel).where(UserModel.is_active.is_(True))
        return await self._paginate(query, page, page_size)

    async def get_by_role(
        self, role_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[User], int]:
        """Get all users assigned a specific role."""
        from regulaforge.infrastructure.persistence.models.role_model import UserRoleModel

        query = (
            select(UserModel)
            .join(UserRoleModel, UserModel.id == UserRoleModel.user_id)
            .where(UserRoleModel.role_id == role_id)
        )
        return await self._paginate(query, page, page_size)

    async def email_exists(self, email: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if an email is already taken."""
        stmt = select(UserModel.id).where(UserModel.email == email)
        if exclude_id:
            stmt = stmt.where(UserModel.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    async def username_exists(self, username: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if a username is already taken."""
        stmt = select(UserModel.id).where(UserModel.username == username)
        if exclude_id:
            stmt = stmt.where(UserModel.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        """Search users with filtering, sorting, and pagination."""
        query = select(UserModel)

        if filters:
            query = self._apply_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        if sort_by:
            sort_col = getattr(UserModel, sort_by, None)
            if sort_col:
                order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
                query = query.order_by(order)
        else:
            query = query.order_by(UserModel.created_at.desc())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]

        return domains, total

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        """Count users matching filters."""
        query = select(func.count(UserModel.id))
        if filters:
            query = self._apply_filters(query, filters)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def _paginate(
        self, query: Select, page: int, page_size: int
    ) -> tuple[list[User], int]:
        """Apply pagination and return domain entities."""
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(UserModel.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    def _apply_filters(self, query: Select, filters: dict[str, Any]) -> Select:
        """Apply dynamic filters to query."""
        filter_map = {
            "email": UserModel.email,
            "username": UserModel.username,
            "is_active": UserModel.is_active,
            "is_superuser": UserModel.is_superuser,
            "tenant_id": UserModel.tenant_id,
        }
        for field, value in filters.items():
            column = filter_map.get(field)
            if column is not None and value is not None:
                query = query.where(column.in_(value)) if isinstance(value, list) else query.where(column == value)
        return query

    def _to_model(self, entity: User) -> UserModel:
        """Convert User domain entity to ORM model."""
        return UserModel(
            id=entity.id,
            email=entity.email,
            username=entity.username,
            password_hash=entity.password_hash,
            full_name=entity.full_name,
            is_active=entity.is_active,
            is_superuser=entity.is_superuser,
            tenant_id=entity.tenant_id,
            last_login_at=entity.last_login_at,
            failed_login_attempts=entity.failed_login_attempts,
            locked_until=entity.locked_until,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            version=entity.version,
        )

    def _to_domain(self, model: UserModel) -> User:
        """Convert ORM model to User domain entity."""
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            full_name=model.full_name,
            tenant_id=model.tenant_id,
            username=model.username,
            is_active=model.is_active,
            is_superuser=model.is_superuser,
            last_login_at=model.last_login_at,
            failed_login_attempts=model.failed_login_attempts,
            locked_until=model.locked_until,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
            version=model.version,
        )

    @staticmethod
    def _update_model(model: UserModel, entity: User) -> None:
        """Update an existing ORM model from a domain entity."""
        model.email = entity.email
        model.username = entity.username
        model.password_hash = entity.password_hash
        model.full_name = entity.full_name
        model.is_active = entity.is_active
        model.is_superuser = entity.is_superuser
        model.tenant_id = entity.tenant_id
        model.last_login_at = entity.last_login_at
        model.failed_login_attempts = entity.failed_login_attempts
        model.locked_until = entity.locked_until
        model.updated_at = entity.updated_at
        model.updated_by = entity.updated_by
        model.version = entity.version
