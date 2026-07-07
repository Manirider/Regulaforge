from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlSourceType,
    DocumentFingerprint,
    DocumentStatus,
    RegulatoryDocument,
)


class CrawlJobRepository(ABC):

    @abstractmethod
    async def save(self, job: CrawlJob) -> None: ...

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> CrawlJob | None: ...

    @abstractmethod
    async def list(
        self,
        source_type: CrawlSourceType | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[builtins.list[CrawlJob], int]: ...

    @abstractmethod
    async def get_last_run(
        self, source_type: CrawlSourceType,
    ) -> CrawlJob | None: ...

    @abstractmethod
    async def get_last_successful_run(
        self, source_type: CrawlSourceType,
    ) -> CrawlJob | None: ...


class DocumentRepository(ABC):

    @abstractmethod
    async def save(self, doc: RegulatoryDocument) -> None: ...

    @abstractmethod
    async def get_by_id(self, doc_id: UUID) -> RegulatoryDocument | None: ...

    @abstractmethod
    async def get_by_external_id(
        self, source_type: CrawlSourceType, external_id: str,
    ) -> RegulatoryDocument | None: ...

    @abstractmethod
    async def get_by_file_hash(self, sha256: str) -> RegulatoryDocument | None: ...

    @abstractmethod
    async def get_by_content_hash(self, content_hash: str) -> builtins.list[RegulatoryDocument]: ...

    @abstractmethod
    async def list(
        self,
        source_type: CrawlSourceType | None = None,
        category: str | None = None,
        status: DocumentStatus | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[builtins.list[RegulatoryDocument], int]: ...

    @abstractmethod
    async def get_latest_version(
        self, source_type: CrawlSourceType, external_id: str,
    ) -> RegulatoryDocument | None: ...

    @abstractmethod
    async def count_by_source(self, source_type: CrawlSourceType) -> int: ...


class FingerprintRepository(ABC):

    @abstractmethod
    async def save(self, fp: DocumentFingerprint) -> None: ...

    @abstractmethod
    async def get_by_document_id(self, doc_id: UUID) -> DocumentFingerprint | None: ...

    @abstractmethod
    async def find_similar(
        self, content_hash: str, threshold: float = 0.95,
    ) -> list[DocumentFingerprint]: ...

    @abstractmethod
    async def exists_by_file_hash(self, sha256: str) -> bool: ...
