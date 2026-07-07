from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import pytest
from regulaforge.ingestion.application.fingerprint_service import DeduplicationService, FingerprintCalculator
from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlJobStatus,
    CrawlSourceConfig,
    CrawlSourceType,
    DocumentCategory,
    DocumentFingerprint,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.domain.repository import (
    CrawlJobRepository,
    DocumentRepository,
    FingerprintRepository,
)


class InMemoryDocumentRepo(DocumentRepository):
    def __init__(self) -> None:
        self._docs: Dict[UUID, RegulatoryDocument] = {}
        self._by_ext_id: Dict[str, RegulatoryDocument] = {}
        self._by_file_hash: Dict[str, RegulatoryDocument] = {}
        self._by_content_hash: Dict[str, List[RegulatoryDocument]] = {}

    async def save(self, doc: RegulatoryDocument) -> None:
        self._docs[doc.id] = doc
        key = f"{doc.source_type.value}:{doc.external_id}"
        self._by_ext_id[key] = doc
        if doc.file_hash_sha256:
            self._by_file_hash[doc.file_hash_sha256] = doc
        if doc.content_hash:
            if doc.content_hash not in self._by_content_hash:
                self._by_content_hash[doc.content_hash] = []
            self._by_content_hash[doc.content_hash].append(doc)

    async def get_by_id(self, doc_id: UUID) -> Optional[RegulatoryDocument]:
        return self._docs.get(doc_id)

    async def get_by_external_id(self, source_type: CrawlSourceType, external_id: str) -> Optional[RegulatoryDocument]:
        return self._by_ext_id.get(f"{source_type.value}:{external_id}")

    async def get_by_file_hash(self, sha256: str) -> Optional[RegulatoryDocument]:
        return self._by_file_hash.get(sha256)

    async def get_by_content_hash(self, content_hash: str) -> List[RegulatoryDocument]:
        return self._by_content_hash.get(content_hash, [])

    async def list(
        self,
        source_type: Optional[CrawlSourceType] = None,
        category: Optional[str] = None,
        status: Optional[DocumentStatus] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[RegulatoryDocument], int]:
        docs = list(self._docs.values())
        if source_type:
            docs = [d for d in docs if d.source_type == source_type]
        if category:
            docs = [d for d in docs if d.category.value == category]
        if status:
            docs = [d for d in docs if d.status == status]
        if since:
            docs = [d for d in docs if d.published_date >= since]
        docs.sort(key=lambda d: d.published_date, reverse=True)
        total = len(docs)
        return docs[offset:offset+limit], total

    async def get_latest_version(self, source_type: CrawlSourceType, external_id: str) -> Optional[RegulatoryDocument]:
        key = f"{source_type.value}:{external_id}"
        doc = self._by_ext_id.get(key)
        return doc

    async def count_by_source(self, source_type: CrawlSourceType) -> int:
        return sum(1 for d in self._docs.values() if d.source_type == source_type)


class InMemoryJobRepo(CrawlJobRepository):
    def __init__(self) -> None:
        self._jobs: Dict[UUID, CrawlJob] = {}

    async def save(self, job: CrawlJob) -> None:
        self._jobs[job.id] = job

    async def get_by_id(self, job_id: UUID) -> Optional[CrawlJob]:
        return self._jobs.get(job_id)

    async def list(
        self,
        source_type: Optional[CrawlSourceType] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[CrawlJob], int]:
        jobs = list(self._jobs.values())
        if source_type:
            jobs = [j for j in jobs if j.source_type == source_type]
        if status:
            jobs = [j for j in jobs if j.status.value == status]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        total = len(jobs)
        return jobs[offset:offset+limit], total

    async def get_last_run(self, source_type: CrawlSourceType) -> Optional[CrawlJob]:
        jobs = [j for j in self._jobs.values() if j.source_type == source_type]
        if not jobs:
            return None
        return max(jobs, key=lambda j: j.created_at)

    async def get_last_successful_run(self, source_type: CrawlSourceType) -> Optional[CrawlJob]:
        jobs = [j for j in self._jobs.values() if j.source_type == source_type and j.status == CrawlJobStatus.COMPLETED]
        if not jobs:
            return None
        return max(jobs, key=lambda j: j.created_at)


class InMemoryFingerprintRepo(FingerprintRepository):
    def __init__(self) -> None:
        self._fps: Dict[UUID, DocumentFingerprint] = {}
        self._by_doc: Dict[UUID, DocumentFingerprint] = {}
        self._by_file_hash: set = set()

    async def save(self, fp: DocumentFingerprint) -> None:
        self._fps[fp.id] = fp
        self._by_doc[fp.document_id] = fp
        if fp.file_hash_sha256:
            self._by_file_hash.add(fp.file_hash_sha256)

    async def get_by_document_id(self, doc_id: UUID) -> Optional[DocumentFingerprint]:
        return self._by_doc.get(doc_id)

    async def find_similar(self, content_hash: str, threshold: float = 0.95) -> List[DocumentFingerprint]:
        return [fp for fp in self._fps.values() if fp.content_hash == content_hash]

    async def exists_by_file_hash(self, sha256: str) -> bool:
        return sha256 in self._by_file_hash


@pytest.fixture
def fp_calculator() -> FingerprintCalculator:
    return FingerprintCalculator()


@pytest.fixture
def dedup_service(fp_calculator) -> DeduplicationService:
    return DeduplicationService(fp_calculator)


@pytest.fixture
def doc_repo() -> InMemoryDocumentRepo:
    return InMemoryDocumentRepo()


@pytest.fixture
def job_repo() -> InMemoryJobRepo:
    return InMemoryJobRepo()


@pytest.fixture
def fp_repo() -> InMemoryFingerprintRepo:
    return InMemoryFingerprintRepo()


@pytest.fixture
def sample_doc_rbi() -> RegulatoryDocument:
    return RegulatoryDocument(
        id=uuid4(),
        source_type=CrawlSourceType.RBI,
        external_id="RBI-2024-001",
        title="Master Direction on KYC",
        category=DocumentCategory.MASTER_DIRECTION,
        url="https://rbi.org.in/circular/kyc",
        published_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        effective_date=datetime(2024, 3, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_doc_sebi() -> RegulatoryDocument:
    return RegulatoryDocument(
        id=uuid4(),
        source_type=CrawlSourceType.SEBI,
        external_id="SEBI-2024-042",
        title="Circular on Insider Trading",
        category=DocumentCategory.CIRCULAR,
        url="https://sebi.gov.in/circular/insider",
        published_date=datetime(2024, 2, 10, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_job() -> CrawlJob:
    return CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI)


@pytest.fixture
def default_config() -> CrawlSourceConfig:
    return CrawlSourceConfig(
        source_type=CrawlSourceType.RBI,
        base_url="https://rbi.org.in",
        list_url="https://rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx",
        concurrent_downloads=2,
    )
