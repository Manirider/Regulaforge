from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlJobStatus,
    CrawlSourceType,
    DocumentCategory,
    DocumentFingerprint,
    DocumentStatus,
    RegulatoryDocument,
)

from tests.ingestion.conftest import (
    InMemoryDocumentRepo,
    InMemoryFingerprintRepo,
    InMemoryJobRepo,
)


class TestInMemoryDocumentRepo:
    @pytest.fixture
    def repo(self) -> InMemoryDocumentRepo:
        return InMemoryDocumentRepo()

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self, repo) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-001",
            title="Test",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/test",
            published_date=datetime.now(timezone.utc),
        )
        await repo.save(doc)
        retrieved = await repo.get_by_id(doc.id)
        assert retrieved is not None
        assert retrieved.external_id == "RBI-001"

    @pytest.mark.asyncio
    async def test_get_by_external_id(self, repo) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.SEBI,
            external_id="SEBI-042",
            title="SEBI Circular",
            category=DocumentCategory.CIRCULAR,
            url="https://sebi.gov.in/circular",
            published_date=datetime.now(timezone.utc),
        )
        await repo.save(doc)
        retrieved = await repo.get_by_external_id(CrawlSourceType.SEBI, "SEBI-042")
        assert retrieved is not None
        assert retrieved.title == "SEBI Circular"

    @pytest.mark.asyncio
    async def test_get_by_file_hash(self, repo) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-HASH",
            title="Hash Test",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/hash",
            published_date=datetime.now(timezone.utc),
            file_hash_sha256="abc123hash",
        )
        await repo.save(doc)
        retrieved = await repo.get_by_file_hash("abc123hash")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_get_by_content_hash(self, repo) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-CONTENT",
            title="Content Hash Test",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/content",
            published_date=datetime.now(timezone.utc),
            content_hash="content456",
        )
        await repo.save(doc)
        results = await repo.get_by_content_hash("content456")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_with_filters(self, repo) -> None:
        for i in range(5):
            doc = RegulatoryDocument(
                id=uuid4(),
                source_type=CrawlSourceType.RBI if i < 3 else CrawlSourceType.SEBI,
                external_id=f"DOC-{i:03d}",
                title=f"Document {i}",
                category=DocumentCategory.CIRCULAR,
                url=f"https://example.com/{i}",
                published_date=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
            )
            await repo.save(doc)
        docs, total = await repo.list(source_type=CrawlSourceType.RBI)
        assert total == 3
        assert len(docs) == 3

    @pytest.mark.asyncio
    async def test_count_by_source(self, repo) -> None:
        for i in range(4):
            await repo.save(RegulatoryDocument(
                id=uuid4(),
                source_type=CrawlSourceType.IRDAI,
                external_id=f"IRDAI-{i}",
                title=f"Doc {i}",
                category=DocumentCategory.CIRCULAR,
                url=f"https://irdai.gov.in/{i}",
                published_date=datetime.now(timezone.utc),
            ))
        count = await repo.count_by_source(CrawlSourceType.IRDAI)
        assert count == 4


class TestInMemoryJobRepo:
    @pytest.fixture
    def repo(self) -> InMemoryJobRepo:
        return InMemoryJobRepo()

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self, repo) -> None:
        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI)
        await repo.save(job)
        retrieved = await repo.get_by_id(job.id)
        assert retrieved is not None
        assert retrieved.source_type == CrawlSourceType.RBI

    @pytest.mark.asyncio
    async def test_get_last_run(self, repo) -> None:
        from datetime import timedelta
        older = CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI, created_at=datetime.now(timezone.utc) - timedelta(seconds=10))
        newer = CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI, created_at=datetime.now(timezone.utc))
        await repo.save(older)
        await repo.save(newer)
        last = await repo.get_last_run(CrawlSourceType.RBI)
        assert last is not None
        assert last.id == newer.id

    @pytest.mark.asyncio
    async def test_get_last_successful_run(self, repo) -> None:
        failed = CrawlJob(id=uuid4(), source_type=CrawlSourceType.SEBI)
        failed.fail("error")
        await repo.save(failed)
        success = CrawlJob(id=uuid4(), source_type=CrawlSourceType.SEBI)
        success.start()
        success.complete()
        await repo.save(success)
        last = await repo.get_last_successful_run(CrawlSourceType.SEBI)
        assert last is not None
        assert last.id == success.id


class TestInMemoryFingerprintRepo:
    @pytest.fixture
    def repo(self) -> InMemoryFingerprintRepo:
        return InMemoryFingerprintRepo()

    @pytest.mark.asyncio
    async def test_save_and_get(self, repo) -> None:
        doc_id = uuid4()
        fp = DocumentFingerprint(
            id=uuid4(),
            document_id=doc_id,
            file_hash_sha256="filehash",
            content_hash="contenthash",
            simhash=12345,
            num_tokens=100,
        )
        await repo.save(fp)
        retrieved = await repo.get_by_document_id(doc_id)
        assert retrieved is not None
        assert retrieved.content_hash == "contenthash"

    @pytest.mark.asyncio
    async def test_exists_by_file_hash(self, repo) -> None:
        fp = DocumentFingerprint(
            id=uuid4(),
            document_id=uuid4(),
            file_hash_sha256="exists_hash",
            content_hash="ch",
            num_tokens=10,
        )
        await repo.save(fp)
        assert await repo.exists_by_file_hash("exists_hash") is True
        assert await repo.exists_by_file_hash("nope") is False
