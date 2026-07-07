from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.config.logging import get_logger
from regulaforge.infrastructure.persistence.models.ingestion_models import (
    CrawlJobModel,
    DocumentFingerprintModel,
    RegulatoryDocumentModel,
)
from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlJobStatus,
    CrawlSourceType,
    DocumentFingerprint,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.domain.repository import (
    CrawlJobRepository,
    DocumentRepository,
    FingerprintRepository,
)

logger = get_logger(__name__)


class SqlAlchemyCrawlJobRepository(CrawlJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: CrawlJob) -> None:
        existing = await self._session.get(CrawlJobModel, job.id)
        if existing:
            existing.started_at = job.started_at
            existing.completed_at = job.completed_at
            existing.status = job.status.value
            existing.documents_found = job.documents_found
            existing.documents_downloaded = job.documents_downloaded
            existing.documents_failed = job.documents_failed
            existing.documents_duplicate = job.documents_duplicate
            existing.error_message = job.error_message
        else:
            model = CrawlJobModel(
                id=job.id,
                source_type=job.source_type.value,
                started_at=job.started_at,
                completed_at=job.completed_at,
                status=job.status.value,
                documents_found=job.documents_found,
                documents_downloaded=job.documents_downloaded,
                documents_failed=job.documents_failed,
                documents_duplicate=job.documents_duplicate,
                error_message=job.error_message,
            )
            self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, job_id: UUID) -> Optional[CrawlJob]:
        model = await self._session.get(CrawlJobModel, job_id)
        return self._to_domain(model) if model else None

    async def list(
        self,
        source_type: Optional[CrawlSourceType] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CrawlJob], int]:
        query = select(CrawlJobModel)
        if source_type:
            query = query.where(CrawlJobModel.source_type == source_type.value)
        if status:
            query = query.where(CrawlJobModel.status == status)
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0
        query = query.order_by(CrawlJobModel.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models], total

    async def get_last_run(self, source_type: CrawlSourceType) -> Optional[CrawlJob]:
        result = await self._session.execute(
            select(CrawlJobModel)
            .where(CrawlJobModel.source_type == source_type.value)
            .order_by(CrawlJobModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_last_successful_run(self, source_type: CrawlSourceType) -> Optional[CrawlJob]:
        result = await self._session.execute(
            select(CrawlJobModel)
            .where(
                and_(
                    CrawlJobModel.source_type == source_type.value,
                    CrawlJobModel.status == CrawlJobStatus.COMPLETED.value,
                )
            )
            .order_by(CrawlJobModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    def _to_domain(self, model: CrawlJobModel) -> CrawlJob:
        return CrawlJob(
            id=model.id,
            source_type=CrawlSourceType(model.source_type),
            started_at=model.started_at,
            completed_at=model.completed_at,
            status=CrawlJobStatus(model.status),
            documents_found=model.documents_found,
            documents_downloaded=model.documents_downloaded,
            documents_failed=model.documents_failed,
            documents_duplicate=model.documents_duplicate,
            error_message=model.error_message,
            created_at=model.created_at,
        )


class SqlAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, doc: RegulatoryDocument) -> None:
        existing = await self._session.get(RegulatoryDocumentModel, doc.id)
        if existing:
            existing.title = doc.title
            existing.category = doc.category.value
            existing.url = doc.url
            existing.published_date = doc.published_date
            existing.effective_date = doc.effective_date
            existing.download_path = doc.download_path
            existing.file_size_bytes = doc.file_size_bytes
            existing.file_hash_sha256 = doc.file_hash_sha256
            existing.content_hash = doc.content_hash
            existing.metadata_json = doc.metadata
            existing.status = doc.status.value
            existing.version = doc.version
            existing.previous_version_id = doc.previous_version_id
        else:
            model = RegulatoryDocumentModel(
                id=doc.id,
                source_type=doc.source_type.value,
                external_id=doc.external_id,
                title=doc.title,
                category=doc.category.value,
                url=doc.url,
                published_date=doc.published_date,
                effective_date=doc.effective_date,
                download_path=doc.download_path,
                file_size_bytes=doc.file_size_bytes,
                file_hash_sha256=doc.file_hash_sha256,
                content_hash=doc.content_hash,
                metadata_json=doc.metadata,
                status=doc.status.value,
                version=doc.version,
                previous_version_id=doc.previous_version_id,
            )
            self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, doc_id: UUID) -> Optional[RegulatoryDocument]:
        model = await self._session.get(RegulatoryDocumentModel, doc_id)
        return self._to_domain(model) if model else None

    async def get_by_external_id(
        self, source_type: CrawlSourceType, external_id: str,
    ) -> Optional[RegulatoryDocument]:
        result = await self._session.execute(
            select(RegulatoryDocumentModel).where(
                and_(
                    RegulatoryDocumentModel.source_type == source_type.value,
                    RegulatoryDocumentModel.external_id == external_id,
                )
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_file_hash(self, sha256: str) -> Optional[RegulatoryDocument]:
        result = await self._session.execute(
            select(RegulatoryDocumentModel).where(
                RegulatoryDocumentModel.file_hash_sha256 == sha256,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_content_hash(self, content_hash: str) -> list[RegulatoryDocument]:
        result = await self._session.execute(
            select(RegulatoryDocumentModel).where(
                RegulatoryDocumentModel.content_hash == content_hash,
            )
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def list(
        self,
        source_type: Optional[CrawlSourceType] = None,
        category: Optional[str] = None,
        status: Optional[DocumentStatus] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[RegulatoryDocument], int]:
        query = select(RegulatoryDocumentModel)
        if source_type:
            query = query.where(RegulatoryDocumentModel.source_type == source_type.value)
        if category:
            query = query.where(RegulatoryDocumentModel.category == category)
        if status:
            query = query.where(RegulatoryDocumentModel.status == status.value)
        if since:
            query = query.where(RegulatoryDocumentModel.published_date >= since)
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0
        query = query.order_by(RegulatoryDocumentModel.published_date.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models], total

    async def get_latest_version(
        self, source_type: CrawlSourceType, external_id: str,
    ) -> Optional[RegulatoryDocument]:
        result = await self._session.execute(
            select(RegulatoryDocumentModel)
            .where(
                and_(
                    RegulatoryDocumentModel.source_type == source_type.value,
                    RegulatoryDocumentModel.external_id == external_id,
                )
            )
            .order_by(RegulatoryDocumentModel.version.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def count_by_source(self, source_type: CrawlSourceType) -> int:
        result = await self._session.execute(
            select(func.count(RegulatoryDocumentModel.id)).where(
                RegulatoryDocumentModel.source_type == source_type.value,
            )
        )
        return result.scalar() or 0

    def _to_domain(self, model: RegulatoryDocumentModel) -> RegulatoryDocument:
        return RegulatoryDocument(
            id=model.id,
            source_type=CrawlSourceType(model.source_type),
            external_id=model.external_id,
            title=model.title,
            category=DocumentCategory(model.category),
            url=model.url,
            published_date=model.published_date,
            effective_date=model.effective_date,
            download_path=model.download_path,
            file_size_bytes=model.file_size_bytes,
            file_hash_sha256=model.file_hash_sha256,
            content_hash=model.content_hash,
            metadata=model.metadata_json,
            status=DocumentStatus(model.status),
            version=model.version,
            previous_version_id=model.previous_version_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


from regulaforge.ingestion.domain.models import DocumentCategory  # noqa: E402


class SqlAlchemyFingerprintRepository(FingerprintRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, fp: DocumentFingerprint) -> None:
        model = DocumentFingerprintModel(
            id=fp.id,
            document_id=fp.document_id,
            file_hash_sha256=fp.file_hash_sha256,
            content_hash=fp.content_hash,
            simhash=fp.simhash,
            num_tokens=fp.num_tokens,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_document_id(self, doc_id: UUID) -> Optional[DocumentFingerprint]:
        result = await self._session.execute(
            select(DocumentFingerprintModel).where(
                DocumentFingerprintModel.document_id == doc_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_similar(
        self, content_hash: str, _threshold: float = 0.95,
    ) -> list[DocumentFingerprint]:
        result = await self._session.execute(
            select(DocumentFingerprintModel).where(
                DocumentFingerprintModel.content_hash == content_hash,
            )
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def exists_by_file_hash(self, sha256: str) -> bool:
        result = await self._session.execute(
            select(DocumentFingerprintModel.id).where(
                DocumentFingerprintModel.file_hash_sha256 == sha256,
            ).limit(1)
        )
        return result.scalar() is not None

    def _to_domain(self, model: DocumentFingerprintModel) -> DocumentFingerprint:
        return DocumentFingerprint(
            id=model.id,
            document_id=model.document_id,
            file_hash_sha256=model.file_hash_sha256,
            content_hash=model.content_hash,
            simhash=model.simhash,
            num_tokens=model.num_tokens,
            created_at=model.created_at,
        )
