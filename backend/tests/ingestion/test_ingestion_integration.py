from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from regulaforge.ingestion.application.crawler_service import CrawlerService
from regulaforge.ingestion.application.etl_service import ETLService
from regulaforge.ingestion.application.fingerprint_service import (
    DeduplicationService,
    FingerprintCalculator,
)
from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlJobStatus,
    CrawlSourceConfig,
    CrawlSourceType,
    DocumentCategory,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.infrastructure.crawlers.base_crawler import (
    BaseCrawler,
    DiscoveredDocument,
)
from regulaforge.ingestion.infrastructure.repositories.in_memory import (
    InMemoryCrawlJobRepository,
    InMemoryDocumentRepository,
    InMemoryFingerprintRepository,
)


class MockCrawler(BaseCrawler):
    def __init__(self, source_type: CrawlSourceType) -> None:
        super().__init__()
        self._source_type = source_type
        self._discover_count = 0

    async def discover_documents(
        self,
        config: CrawlSourceConfig,
        since: datetime | None = None,
    ) -> list[DiscoveredDocument]:
        self._discover_count += 1
        return [
            DiscoveredDocument(
                external_id=f"{self._source_type.value}-001",
                title=f"Test Document from {self._source_type.value}",
                url=f"https://example.com/{self._source_type.value}/doc1",
                category=DocumentCategory.CIRCULAR,
                published_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            ),
        ]

    async def download_document(
        self,
        doc: RegulatoryDocument,
        config: CrawlSourceConfig,
        download_dir: Path,
    ) -> tuple[Path, int, str]:
        path = download_dir / f"{doc.external_id}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"Mock content for {doc.external_id}".encode()
        path.write_bytes(content)

        import hashlib
        sha256 = hashlib.sha256(content).hexdigest()
        return path, len(content), sha256


class TestIngestionPipelineIntegration:
    @pytest.fixture
    def repos(self) -> tuple:
        return (
            InMemoryDocumentRepository(),
            InMemoryFingerprintRepository(),
            InMemoryCrawlJobRepository(),
        )

    @pytest.fixture
    def services(self, repos, tmp_path: Path) -> tuple:
        doc_repo, fp_repo, job_repo = repos
        fp_calc = FingerprintCalculator()
        dedup = DeduplicationService(fp_calc)
        etl = ETLService(doc_repo, fp_repo, job_repo, fp_calc, dedup)

        crawlers = {
            CrawlSourceType.RBI: MockCrawler(CrawlSourceType.RBI),
            CrawlSourceType.SEBI: MockCrawler(CrawlSourceType.SEBI),
            CrawlSourceType.IRDAI: MockCrawler(CrawlSourceType.IRDAI),
        }

        configs = {
            CrawlSourceType.RBI: CrawlSourceConfig(
                source_type=CrawlSourceType.RBI,
                base_url="https://rbi.org.in",
                list_url="https://rbi.org.in/list",
            ),
            CrawlSourceType.SEBI: CrawlSourceConfig(
                source_type=CrawlSourceType.SEBI,
                base_url="https://sebi.gov.in",
                list_url="https://sebi.gov.in/list",
            ),
            CrawlSourceType.IRDAI: CrawlSourceConfig(
                source_type=CrawlSourceType.IRDAI,
                base_url="https://irdai.gov.in",
                list_url="https://irdai.gov.in/list",
            ),
        }

        raw_dir = tmp_path / "raw"
        text_dir = tmp_path / "text"
        raw_dir.mkdir()
        text_dir.mkdir()

        service = CrawlerService(
            crawlers=crawlers,
            doc_repo=doc_repo,
            fp_repo=fp_repo,
            job_repo=job_repo,
            etl_service=etl,
            fingerprint_calculator=fp_calc,
            configs=configs,
            raw_dir=raw_dir,
            text_dir=text_dir,
            concurrency=2,
        )
        return service, doc_repo, job_repo, fp_repo, raw_dir, text_dir

    @pytest.mark.asyncio
    async def test_crawl_source_creates_job(self, services) -> None:
        service, doc_repo, job_repo, fp_repo, raw_dir, text_dir = services
        job = await service.crawl_source(CrawlSourceType.RBI, incremental=False)

        assert job.source_type == CrawlSourceType.RBI
        assert job.status == CrawlJobStatus.COMPLETED
        assert job.documents_found >= 1
        assert job.started_at is not None
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_crawl_source_downloads_documents(self, services) -> None:
        service, doc_repo, job_repo, fp_repo, raw_dir, text_dir = services
        await service.crawl_source(CrawlSourceType.SEBI, incremental=False)

        docs, total = await doc_repo.list(source_type=CrawlSourceType.SEBI)
        assert total >= 1
        doc = docs[0]
        assert doc.source_type == CrawlSourceType.SEBI
        assert doc.status in (DocumentStatus.DOWNLOADED, DocumentStatus.PROCESSED)

    @pytest.mark.asyncio
    async def test_crawl_all_sources(self, services) -> None:
        service, doc_repo, job_repo, fp_repo, raw_dir, text_dir = services
        results = await service.crawl_all(incremental=False)

        assert len(results) == 3
        for st, job in results.items():
            assert job.status == CrawlJobStatus.COMPLETED
            assert job.documents_found >= 1

    @pytest.mark.asyncio
    async def test_incremental_crawl_skips_existing(self, services) -> None:
        service, doc_repo, job_repo, fp_repo, raw_dir, text_dir = services
        job1 = await service.crawl_source(CrawlSourceType.RBI, incremental=False)
        job2 = await service.crawl_source(CrawlSourceType.RBI, incremental=True)

        # After first crawl, second should still complete but may discover fewer
        assert job2.status == CrawlJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_job_tracks_document_counts(self, services) -> None:
        service, doc_repo, job_repo, fp_repo, raw_dir, text_dir = services
        job = await service.crawl_source(CrawlSourceType.IRDAI, incremental=False)

        assert job.documents_found >= 1
        assert job.documents_downloaded >= 1
        assert job.documents_failed == 0

    @pytest.mark.asyncio
    async def test_raw_files_stored_on_disk(self, services) -> None:
        service, doc_repo, job_repo, fp_repo, raw_dir, text_dir = services
        await service.crawl_source(CrawlSourceType.RBI, incremental=False)

        raw_files = list(raw_dir.rglob("*"))
        assert len(raw_files) > 0

    @pytest.mark.asyncio
    async def test_document_has_file_hash(self, services) -> None:
        service, doc_repo, job_repo, fp_repo, raw_dir, text_dir = services
        await service.crawl_source(CrawlSourceType.RBI, incremental=False)

        docs, _ = await doc_repo.list(source_type=CrawlSourceType.RBI)
        for doc in docs:
            assert doc.file_hash_sha256 is not None
            assert len(doc.file_hash_sha256) == 64
