from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from regulaforge.ingestion.domain.events import (
    CrawlCompleted,
    CrawlStarted,
    DocumentDownloaded,
    DocumentDuplicateFound,
    DocumentVersionCreated,
)
from regulaforge.ingestion.domain.models import CrawlSourceType


class TestDomainEvents:
    def test_crawl_started_event(self) -> None:
        job_id = uuid4()
        ts = datetime.now(timezone.utc)
        event = CrawlStarted(job_id=job_id, source_type=CrawlSourceType.RBI, timestamp=ts)
        d = event.to_dict()
        assert d["job_id"] == str(job_id)
        assert d["source_type"] == "rbi"
        assert d["event_type"] == "crawl_started"

    def test_crawl_completed_event(self) -> None:
        job_id = uuid4()
        ts = datetime.now(timezone.utc)
        event = CrawlCompleted(
            job_id=job_id,
            source_type=CrawlSourceType.SEBI,
            documents_found=15,
            documents_downloaded=12,
            documents_failed=1,
            documents_duplicate=2,
            duration_seconds=45.5,
            timestamp=ts,
        )
        d = event.to_dict()
        assert d["documents_found"] == 15
        assert d["documents_downloaded"] == 12
        assert d["duration_seconds"] == 45.5
        assert d["event_type"] == "crawl_completed"

    def test_document_downloaded_event(self) -> None:
        doc_id = uuid4()
        ts = datetime.now(timezone.utc)
        event = DocumentDownloaded(
            document_id=doc_id,
            source_type=CrawlSourceType.IRDAI,
            external_id="IRDAI-001",
            title="Test Circular",
            file_size_bytes=2048,
            file_hash_sha256="sha256hash",
            timestamp=ts,
        )
        d = event.to_dict()
        assert d["external_id"] == "IRDAI-001"
        assert d["file_size_bytes"] == 2048
        assert d["file_hash_sha256"] == "sha256hash"

    def test_document_duplicate_event(self) -> None:
        doc_id = uuid4()
        existing_id = uuid4()
        ts = datetime.now(timezone.utc)
        event = DocumentDuplicateFound(
            document_id=doc_id,
            existing_document_id=existing_id,
            source_type=CrawlSourceType.RBI,
            external_id="RBI-DUP",
            file_hash_sha256="dup123",
            timestamp=ts,
        )
        d = event.to_dict()
        assert d["existing_document_id"] == str(existing_id)
        assert d["file_hash_sha256"] == "dup123"

    def test_document_version_event(self) -> None:
        doc_id = uuid4()
        prev_id = uuid4()
        ts = datetime.now(timezone.utc)
        event = DocumentVersionCreated(
            document_id=doc_id,
            source_type=CrawlSourceType.SEBI,
            external_id="SEBI-V2",
            version=2,
            previous_version_id=prev_id,
            timestamp=ts,
        )
        d = event.to_dict()
        assert d["version"] == 2
        assert d["previous_version_id"] == str(prev_id)
