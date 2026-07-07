from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

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
from regulaforge.ingestion.infrastructure.storage.document_store import DocumentStore

from tests.ingestion.conftest import (
    InMemoryDocumentRepo,
    InMemoryFingerprintRepo,
    InMemoryJobRepo,
)


class MockCrawler(BaseCrawler):
    def __init__(self, discovered: Optional[List[DiscoveredDocument]] = None) -> None:
        self._discovered = discovered or []
        self.download_calls: List[RegulatoryDocument] = []

    async def discover_documents(
        self,
        config: CrawlSourceConfig,
        since: Optional[datetime] = None,
    ) -> List[DiscoveredDocument]:
        return self._discovered

    async def download_document(
        self,
        doc: RegulatoryDocument,
        config: CrawlSourceConfig,
        download_dir: Path,
    ) -> Tuple[Path, int, str]:
        self.download_calls.append(doc)
        dl_path = download_dir / f"{doc.external_id}.pdf"
        dl_path.parent.mkdir(parents=True, exist_ok=True)
        dl_path.write_text(f"mock content for {doc.external_id}")
        return dl_path, dl_path.stat().st_size, f"sha256_{doc.external_id}"


class TestCrawlerService:
    @pytest.fixture
    def mock_crawler(self) -> MockCrawler:
        return MockCrawler(
            discovered=[
                DiscoveredDocument(
                    external_id="RBI-CIR-001",
                    title="KYC Circular 2024",
                    url="https://rbi.org.in/circular1.pdf",
                    category=DocumentCategory.CIRCULAR,
                    published_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
                ),
                DiscoveredDocument(
                    external_id="RBI-CIR-002",
                    title="Risk Management Guidelines",
                    url="https://rbi.org.in/circular2.pdf",
                    category=DocumentCategory.GUIDELINE,
                    published_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
                ),
            ]
        )

    @pytest.fixture
    def configs(self) -> Dict[CrawlSourceType, CrawlSourceConfig]:
        return {
            CrawlSourceType.RBI: CrawlSourceConfig(
                source_type=CrawlSourceType.RBI,
                base_url="https://rbi.org.in",
                list_url="https://rbi.org.in/list",
                concurrent_downloads=2,
            ),
        }

    @pytest.fixture
    def crawler_service(
        self,
        mock_crawler,
        configs,
        tmp_path,
    ) -> CrawlerService:
        doc_repo = InMemoryDocumentRepo()
        fp_repo = InMemoryFingerprintRepo()
        job_repo = InMemoryJobRepo()
        fp_calc = FingerprintCalculator()
        dedup = DeduplicationService(fp_calc)
        etl = ETLService(doc_repo, fp_repo, job_repo, fp_calc, dedup)
        store = DocumentStore(tmp_path / "ingestion_data")

        return CrawlerService(
            crawlers={CrawlSourceType.RBI: mock_crawler},
            doc_repo=doc_repo,
            fp_repo=fp_repo,
            job_repo=job_repo,
            etl_service=etl,
            fingerprint_calculator=fp_calc,
            configs=configs,
            raw_dir=store._raw_dir,
            text_dir=store._text_dir,
            concurrency=2,
        )

    @pytest.mark.asyncio
    async def test_crawl_source_discovers_and_downloads(self, crawler_service, mock_crawler) -> None:
        job = await crawler_service.crawl_source(CrawlSourceType.RBI, incremental=False)

        assert job.status == CrawlJobStatus.COMPLETED
        assert job.documents_found == 2
        assert job.documents_downloaded == 2
        assert job.documents_failed == 0
        assert len(mock_crawler.download_calls) == 2

    @pytest.mark.asyncio
    async def test_crawl_source_with_existing_hashes_skips_duplicates(
        self, crawler_service, mock_crawler, configs
    ) -> None:
        doc_repo = crawler_service._doc_repo
        existing = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-CIR-001",
            title="KYC Circular 2024",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/circular1.pdf",
            published_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            status=DocumentStatus.DOWNLOADED,
            file_hash_sha256="sha256_RBI-CIR-001",
        )
        await doc_repo.save(existing)

        job = await crawler_service.crawl_source(CrawlSourceType.RBI, incremental=False)

        assert job.documents_found == 2
        assert job.documents_downloaded == 1 or job.documents_duplicate >= 1

    @pytest.mark.asyncio
    async def test_crawl_all_sources(self, mock_crawler, configs, tmp_path) -> None:
        doc_repo = InMemoryDocumentRepo()
        fp_repo = InMemoryFingerprintRepo()
        job_repo = InMemoryJobRepo()
        fp_calc = FingerprintCalculator()
        dedup = DeduplicationService(fp_calc)
        etl = ETLService(doc_repo, fp_repo, job_repo, fp_calc, dedup)
        store = DocumentStore(tmp_path / "ingestion_data")

        configs_all = {
            CrawlSourceType.RBI: CrawlSourceConfig(
                source_type=CrawlSourceType.RBI, base_url="", list_url="",
            ),
            CrawlSourceType.SEBI: CrawlSourceConfig(
                source_type=CrawlSourceType.SEBI, base_url="", list_url="",
            ),
            CrawlSourceType.IRDAI: CrawlSourceConfig(
                source_type=CrawlSourceType.IRDAI, base_url="", list_url="",
            ),
        }

        service = CrawlerService(
            crawlers={
                CrawlSourceType.RBI: mock_crawler,
                CrawlSourceType.SEBI: MockCrawler(discovered=[]),
                CrawlSourceType.IRDAI: MockCrawler(discovered=[]),
            },
            doc_repo=doc_repo,
            fp_repo=fp_repo,
            job_repo=job_repo,
            etl_service=etl,
            fingerprint_calculator=fp_calc,
            configs=configs_all,
            raw_dir=store._raw_dir,
            text_dir=store._text_dir,
        )

        results = await service.crawl_all(incremental=False)
        assert set(results.keys()) == {CrawlSourceType.RBI, CrawlSourceType.SEBI, CrawlSourceType.IRDAI}

    @pytest.mark.asyncio
    async def test_crawl_job_persisted(self, crawler_service) -> None:
        job = await crawler_service.crawl_source(CrawlSourceType.RBI)
        saved_job = await crawler_service._job_repo.get_by_id(job.id)
        assert saved_job is not None
        assert saved_job.status == CrawlJobStatus.COMPLETED
        assert saved_job.documents_found == 2
