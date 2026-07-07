"""
In-memory implementations of all ingestion repository interfaces.

Used by the CLI (``commands.py``) and integration tests.  NOT for
production use — persists nothing across restarts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

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


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, RegulatoryDocument] = {}

    async def save(self, doc: RegulatoryDocument) -> None:
        self._store[doc.id] = doc

    async def get_by_id(self, doc_id: UUID) -> RegulatoryDocument | None:
        return self._store.get(doc_id)

    async def get_by_external_id(
        self, source_type: CrawlSourceType, external_id: str
    ) -> RegulatoryDocument | None:
        for doc in self._store.values():
            if doc.source_type == source_type and doc.external_id == external_id:
                return doc
        return None

    async def get_by_file_hash(self, sha256: str) -> RegulatoryDocument | None:
        for doc in self._store.values():
            if doc.file_hash_sha256 == sha256:
                return doc
        return None

    async def get_by_content_hash(self, content_hash: str) -> list[RegulatoryDocument]:
        return [
            doc
            for doc in self._store.values()
            if doc.content_hash == content_hash
        ]

    async def list(
        self,
        source_type: CrawlSourceType | None = None,
        category: str | None = None,
        status: DocumentStatus | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[RegulatoryDocument], int]:
        docs = list(self._store.values())
        if source_type:
            docs = [d for d in docs if d.source_type == source_type]
        if category:
            docs = [d for d in docs if d.category == category]
        if status:
            docs = [d for d in docs if d.status == status]
        if since:
            docs = [d for d in docs if d.created_at >= since]
        total = len(docs)
        return docs[offset : offset + limit], total

    async def get_latest_version(
        self, source_type: CrawlSourceType, external_id: str
    ) -> RegulatoryDocument | None:
        matching = [
            d
            for d in self._store.values()
            if d.source_type == source_type and d.external_id == external_id
        ]
        matching.sort(
            key=lambda d: d.version if d.version else 0,
            reverse=True,
        )
        return matching[0] if matching else None

    async def count_by_source(self, source_type: CrawlSourceType) -> int:
        return sum(1 for d in self._store.values() if d.source_type == source_type)


class InMemoryFingerprintRepository(FingerprintRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, DocumentFingerprint] = {}

    async def save(self, fp: DocumentFingerprint) -> None:
        self._store[fp.id] = fp

    async def get_by_document_id(self, doc_id: UUID) -> DocumentFingerprint | None:
        for fp in self._store.values():
            if fp.document_id == doc_id:
                return fp
        return None

    async def find_similar(
        self, content_hash: str, threshold: float = 0.95
    ) -> list[DocumentFingerprint]:
        return [
            fp for fp in self._store.values() if fp.content_hash == content_hash
        ]

    async def exists_by_file_hash(self, sha256: str) -> bool:
        return any(
            fp.file_hash_sha256 == sha256 for fp in self._store.values()
        )


class InMemoryCrawlJobRepository(CrawlJobRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, CrawlJob] = {}

    async def save(self, job: CrawlJob) -> None:
        self._store[job.id] = job

    async def get_by_id(self, job_id: UUID) -> CrawlJob | None:
        return self._store.get(job_id)

    async def list(
        self,
        source_type: CrawlSourceType | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CrawlJob], int]:
        jobs = list(self._store.values())
        if source_type:
            jobs = [j for j in jobs if j.source_type == source_type]
        if status:
            jobs = [j for j in jobs if j.status.value == status]
        total = len(jobs)
        return jobs[offset : offset + limit], total

    async def get_last_successful_run(
        self, source_type: CrawlSourceType
    ) -> CrawlJob | None:
        matching = [
            j
            for j in self._store.values()
            if j.source_type == source_type and j.status == CrawlJobStatus.COMPLETED
        ]
        matching.sort(
            key=lambda j: j.started_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return matching[0] if matching else None

    async def get_last_run(
        self, source_type: CrawlSourceType
    ) -> CrawlJob | None:
        matching = [
            j for j in self._store.values() if j.source_type == source_type
        ]
        matching.sort(
            key=lambda j: j.started_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return matching[0] if matching else None
