"""SQLAlchemy-based document repository implementation."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.config.logging import get_logger
from regulaforge.domain.entities.document import Document
from regulaforge.domain.repositories.base import EntityNotFoundError, RepositoryError
from regulaforge.domain.repositories.document_repository import DocumentRepository
from regulaforge.infrastructure.persistence.models.document_model import DocumentModel

logger = get_logger(__name__)


class SqlAlchemyDocumentRepository(DocumentRepository):
    """PostgreSQL-backed document repository using SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entity: Document) -> Document:
        try:
            existing = await self._session.get(DocumentModel, entity.id)
            if existing:
                existing.title = entity.title
                existing.description = entity.description
                existing.tags = entity.tags
                existing.extra_metadata = entity._metadata
                existing.is_verified = entity.is_verified
                existing.verified_by = entity.verified_by
                existing.verified_at = entity.verified_at
                existing.processing_status = entity.processing_status
                existing.extracted_text = entity.extracted_text
                existing.updated_by = entity.updated_by
                existing.version = entity.version
            else:
                model = DocumentModel(
                    id=entity.id,
                    title=entity.title,
                    file_name=entity.file_name,
                    file_path=entity.file_path,
                    mime_type=entity.mime_type,
                    file_size_bytes=entity.file_size_bytes,
                    artifact_type=entity.artifact_type.value if hasattr(entity.artifact_type, 'value') else entity.artifact_type,  # noqa: E501
                    tenant_id=entity.tenant_id,
                    uploaded_by=entity.uploaded_by,
                    description=entity.description,
                    tags=entity.tags,
                    checksum=entity._checksum,
                    extra_metadata=entity._metadata,
                    is_verified=entity.is_verified,
                    verified_by=entity.verified_by,
                    verified_at=entity.verified_at,
                    processing_status=entity.processing_status,
                    extracted_text=entity.extracted_text,
                    created_by=entity.created_by,
                    updated_by=entity.updated_by,
                    version=entity.version,
                )
                self._session.add(model)
            await self._session.flush()
            return entity
        except Exception as e:
            logger.error("Failed to save document %s: %s", entity.id, e)
            raise RepositoryError(f"Failed to save document: {e}", e)

    async def get_by_id(self, document_id: UUID) -> Optional[Document]:
        try:
            model = await self._session.get(DocumentModel, document_id)
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get document %s: %s", document_id, e)
            raise RepositoryError(f"Failed to get document: {e}", e)

    async def delete(self, document_id: UUID) -> None:
        try:
            model = await self._session.get(DocumentModel, document_id)
            if not model:
                raise EntityNotFoundError("Document", document_id)
            await self._session.delete(model)
            await self._session.flush()
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to delete document %s: %s", document_id, e)
            raise RepositoryError(f"Failed to delete document: {e}", e)

    async def exists(self, document_id: UUID) -> bool:
        result = await self._session.execute(
            select(DocumentModel.id).where(DocumentModel.id == document_id)
        )
        return result.scalar() is not None

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        query = select(DocumentModel)

        if filters:
            query = self._apply_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        if sort_by:
            sort_col = getattr(DocumentModel, sort_by, None)
            if sort_col:
                order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
                query = query.order_by(order)
        else:
            query = query.order_by(DocumentModel.created_at.desc())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        query = select(func.count(DocumentModel.id))
        if filters:
            query = self._apply_filters(query, filters)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_by_tenant(
        self, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[Document], int]:
        query = select(DocumentModel).where(
            DocumentModel.tenant_id == tenant_id
        )
        return await self._paginate(query, page, page_size)

    async def get_by_artifact_type(
        self, artifact_type: str, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[Document], int]:
        query = select(DocumentModel).where(
            DocumentModel.artifact_type == artifact_type,
            DocumentModel.tenant_id == tenant_id,
        )
        return await self._paginate(query, page, page_size)

    async def get_by_checksum(self, checksum: str) -> Optional[Document]:
        result = await self._session.execute(
            select(DocumentModel).where(
                DocumentModel.checksum == checksum,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def _paginate(
        self, query, page: int, page_size: int
    ) -> tuple[list[Document], int]:
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(DocumentModel.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        models = result.scalars().all()
        domains = [self._to_domain(m) for m in models if m]
        return domains, total

    def _apply_filters(self, query, filters: dict[str, Any]):
        filter_map = {
            "tenant_id": DocumentModel.tenant_id,
            "artifact_type": DocumentModel.artifact_type,
            "processing_status": DocumentModel.processing_status,
            "is_verified": DocumentModel.is_verified,
        }
        for field, value in filters.items():
            column = filter_map.get(field)
            if column is not None and value is not None:
                query = query.where(column == value)
        return query

    def _to_domain(self, model: DocumentModel) -> Document:
        from regulaforge.config.constants import ArtifactType

        return Document(
            id=model.id,
            title=model.title,
            file_name=model.file_name,
            file_path=model.file_path,
            mime_type=model.mime_type,
            file_size_bytes=model.file_size_bytes,
            artifact_type=ArtifactType(model.artifact_type),
            tenant_id=model.tenant_id,
            uploaded_by=model.uploaded_by,
            description=model.description,
            tags=model.tags,
            checksum=model.checksum,
            metadata=model.extra_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
            version=model.version,
        )
