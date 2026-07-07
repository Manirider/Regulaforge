from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
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


class TestDocumentLifecycle:
    def test_create_regulatory_document(self) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-001",
            title="Test Circular",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/test",
            published_date=datetime.now(timezone.utc),
        )
        assert doc.status == DocumentStatus.PENDING_DOWNLOAD
        assert doc.version == 1
        assert doc.previous_version_id is None

    def test_mark_downloaded(self) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-001",
            title="Test",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/test",
            published_date=datetime.now(timezone.utc),
        )
        doc.mark_downloaded("/data/rbi-001.pdf", 1024, "abc123")
        assert doc.status == DocumentStatus.DOWNLOADED
        assert doc.download_path == "/data/rbi-001.pdf"
        assert doc.file_size_bytes == 1024
        assert doc.file_hash_sha256 == "abc123"

    def test_mark_processed(self) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.SEBI,
            external_id="SEBI-001",
            title="Test",
            category=DocumentCategory.CIRCULAR,
            url="https://sebi.gov.in/test",
            published_date=datetime.now(timezone.utc),
        )
        doc.mark_processed("content_hash_xyz", {"num_pages": 5})
        assert doc.status == DocumentStatus.PROCESSED
        assert doc.content_hash == "content_hash_xyz"
        assert doc.metadata["num_pages"] == 5

    def test_mark_duplicate(self) -> None:
        existing_id = uuid4()
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.IRDAI,
            external_id="IRDAI-001",
            title="Test",
            category=DocumentCategory.CIRCULAR,
            url="https://irdai.gov.in/test",
            published_date=datetime.now(timezone.utc),
        )
        doc.mark_duplicate(existing_id)
        assert doc.status == DocumentStatus.DUPLICATE
        assert doc.previous_version_id == existing_id

    def test_mark_failed(self) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-FAIL",
            title="Fail",
            category=DocumentCategory.OTHER,
            url="https://rbi.org.in/fail",
            published_date=datetime.now(timezone.utc),
        )
        doc.mark_failed()
        assert doc.status == DocumentStatus.FAILED

    def test_document_serialization(self) -> None:
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-001",
            title="Test",
            category=DocumentCategory.MASTER_DIRECTION,
            url="https://rbi.org.in/test",
            published_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            effective_date=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        doc.mark_downloaded("/data/test.pdf", 2048, "sha256hash")
        d = doc.to_dict()
        assert d["source_type"] == "rbi"
        assert d["category"] == "master_direction"
        assert d["file_size_bytes"] == 2048
        assert d["file_hash_sha256"] == "sha256hash"
        assert d["status"] == "downloaded"

    def test_document_versioning(self) -> None:
        prev_id = uuid4()
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-V2",
            title="Updated Circular",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/v2",
            published_date=datetime.now(timezone.utc),
            version=2,
            previous_version_id=prev_id,
        )
        assert doc.version == 2
        assert doc.previous_version_id == prev_id


class TestCrawlJobLifecycle:
    def test_create_job(self) -> None:
        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI)
        assert job.status == CrawlJobStatus.PENDING
        assert job.documents_found == 0
        assert job.documents_downloaded == 0

    def test_job_start(self) -> None:
        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.SEBI)
        job.start()
        assert job.status == CrawlJobStatus.RUNNING
        assert job.started_at is not None

    def test_job_complete(self) -> None:
        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.IRDAI)
        job.start()
        job.documents_found = 10
        job.documents_downloaded = 8
        job.documents_duplicate = 2
        job.complete()
        assert job.status == CrawlJobStatus.COMPLETED
        assert job.completed_at is not None

    def test_job_fail(self) -> None:
        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI)
        job.start()
        job.fail("Connection timeout")
        assert job.status == CrawlJobStatus.FAILED
        assert job.error_message == "Connection timeout"

    def test_job_serialization(self) -> None:
        job = CrawlJob(id=uuid4(), source_type=CrawlSourceType.RBI)
        job.start()
        job.complete()
        d = job.to_dict()
        assert d["source_type"] == "rbi"
        assert d["status"] == "completed"
        assert d["started_at"] is not None
        assert d["completed_at"] is not None


class TestDocumentFingerprint:
    def test_create_fingerprint(self) -> None:
        fp = DocumentFingerprint(
            id=uuid4(),
            document_id=uuid4(),
            file_hash_sha256="filehash123",
            content_hash="contenthash456",
            simhash=1234567890,
            num_tokens=250,
        )
        assert fp.file_hash_sha256 == "filehash123"
        assert fp.content_hash == "contenthash456"
        assert fp.num_tokens == 250


class TestCrawlSourceConfig:
    def test_default_values(self) -> None:
        cfg = CrawlSourceConfig(
            source_type=CrawlSourceType.RBI,
            base_url="https://rbi.org.in",
            list_url="https://rbi.org.in/list",
        )
        assert cfg.enabled is True
        assert cfg.crawl_interval_minutes == 360
        assert cfg.max_retries == 3
        assert cfg.concurrent_downloads == 4

    def test_custom_values(self) -> None:
        cfg = CrawlSourceConfig(
            source_type=CrawlSourceType.SEBI,
            base_url="https://sebi.gov.in",
            list_url="https://sebi.gov.in/list",
            enabled=False,
            crawl_interval_minutes=720,
            max_retries=5,
            concurrent_downloads=2,
        )
        assert cfg.enabled is False
        assert cfg.crawl_interval_minutes == 720
        assert cfg.concurrent_downloads == 2
