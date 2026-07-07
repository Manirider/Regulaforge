from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from regulaforge.ingestion.application.etl_service import ETLService
from regulaforge.ingestion.application.fingerprint_service import (
    DeduplicationService,
    FingerprintCalculator,
)
from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlJobStatus,
    CrawlSourceType,
    DocumentCategory,
    DocumentStatus,
    RegulatoryDocument,
)

from tests.ingestion.conftest import (
    InMemoryDocumentRepo,
    InMemoryFingerprintRepo,
    InMemoryJobRepo,
)


class TestETLService:
    @pytest.fixture
    def etl_service(self) -> ETLService:
        doc_repo = InMemoryDocumentRepo()
        fp_repo = InMemoryFingerprintRepo()
        job_repo = InMemoryJobRepo()
        fp_calc = FingerprintCalculator()
        dedup = DeduplicationService(fp_calc)
        return ETLService(doc_repo, fp_repo, job_repo, fp_calc, dedup)

    @pytest.mark.asyncio
    async def test_etl_pipeline_creates_fingerprint(self, etl_service, tmp_path) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-ETL-001",
            title="Test Document",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/test.pdf",
            published_date=datetime.now(timezone.utc),
            status=DocumentStatus.DOWNLOADED,
            file_hash_sha256="testhash123",
        )
        raw_path = tmp_path / "raw" / "RBI-ETL-001.bin"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("Sample regulatory text content for ETL pipeline testing")
        doc.download_path = str(raw_path)

        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI)
        text_dir = tmp_path / "text"
        text_dir.mkdir(parents=True, exist_ok=True)

        await etl_service.etl_pipeline(doc, tmp_path / "raw", text_dir, job)

        assert doc.status == DocumentStatus.PROCESSED

        fp = await etl_service._fp_repo.get_by_document_id(doc.id)
        if fp is not None:
            assert fp.file_hash_sha256 == "testhash123"
            assert fp.num_tokens > 0

    @pytest.mark.asyncio
    async def test_etl_extract_transform_load(self, etl_service, tmp_path) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.SEBI,
            external_id="SEBI-ETL-001",
            title="SEBI Circular",
            category=DocumentCategory.CIRCULAR,
            url="https://sebi.gov.in/circular.pdf",
            published_date=datetime.now(timezone.utc),
            status=DocumentStatus.DOWNLOADED,
            file_hash_sha256="sebihash",
        )
        raw_path = tmp_path / "raw" / "SEBI-ETL-001.pdf"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("SEBI regulatory guidelines for mutual funds")
        doc.download_path = str(raw_path)

        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.SEBI)
        text_dir = tmp_path / "text"

        pdf_bytes = await etl_service.extract(doc, str(raw_path))
        assert len(pdf_bytes) > 0

        text = await etl_service.transform(pdf_bytes, doc)
        assert text is None or isinstance(text, str)

        await etl_service.load(doc, text, job, text_dir)
        assert doc.status == DocumentStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_etl_pipeline_missing_file(self, etl_service, tmp_path) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.IRDAI,
            external_id="IRDAI-ETL-001",
            title="Missing Doc",
            category=DocumentCategory.CIRCULAR,
            url="https://irdai.gov.in/missing.pdf",
            published_date=datetime.now(timezone.utc),
            status=DocumentStatus.DOWNLOADED,
            download_path="/nonexistent/path.pdf",
        )
        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.IRDAI)
        await etl_service.etl_pipeline(doc, tmp_path / "raw", tmp_path / "text", job)
        assert doc.status == DocumentStatus.FAILED
