from __future__ import annotations

from pathlib import Path

import pytest
from regulaforge.ingestion.domain.models import CrawlSourceType
from regulaforge.ingestion.infrastructure.storage.document_store import DocumentStore


class TestDocumentStore:
    @pytest.fixture
    def store(self, tmp_path) -> DocumentStore:
        return DocumentStore(tmp_path / "ingestion_data")

    def test_create_store_creates_directories(self, tmp_path) -> None:
        store = DocumentStore(tmp_path / "new_store")
        assert (tmp_path / "new_store" / "raw").exists()
        assert (tmp_path / "new_store" / "text").exists()
        assert (tmp_path / "new_store" / "metadata").exists()
        assert (tmp_path / "new_store" / "versions").exists()

    def test_source_raw_dir(self, store) -> None:
        d = store.source_raw_dir(CrawlSourceType.RBI)
        assert d.name == "rbi"
        assert d.parent.name == "raw"

    def test_store_raw_pdf(self, store) -> None:
        path = store.store_raw_pdf(CrawlSourceType.SEBI, "doc123", b"pdf content")
        assert path.exists()
        assert path.read_bytes() == b"pdf content"

    def test_store_and_get_text(self, store) -> None:
        store.store_text(CrawlSourceType.IRDAI, "doc456", "extracted text content")
        text_path = store.get_text_path(CrawlSourceType.IRDAI, "doc456")
        assert text_path is not None
        assert text_path.read_text(encoding="utf-8") == "extracted text content"

    def test_store_metadata(self, store) -> None:
        meta = {"title": "Test", "pages": 5}
        store.store_metadata(CrawlSourceType.RBI, "meta001", meta)
        meta_path = store.get_metadata_path(CrawlSourceType.RBI, "meta001")
        assert meta_path is not None
        assert "pages" in meta_path.read_text(encoding="utf-8")

    def test_get_raw_path_missing(self, store) -> None:
        assert store.get_raw_path(CrawlSourceType.RBI, "nonexistent") is None

    def test_list_raw(self, store) -> None:
        store.store_raw_pdf(CrawlSourceType.RBI, "a", b"aaa")
        store.store_raw_pdf(CrawlSourceType.RBI, "b", b"bbb")
        files = store.list_raw(CrawlSourceType.RBI)
        assert len(files) == 2

    def test_total_size(self, store) -> None:
        store.store_raw_pdf(CrawlSourceType.RBI, "a", b"12345")
        store.store_raw_pdf(CrawlSourceType.SEBI, "b", b"67890")
        assert store.total_size_bytes() == 10

    def test_file_count(self, store) -> None:
        store.store_raw_pdf(CrawlSourceType.RBI, "a", b"aaa")
        store.store_raw_pdf(CrawlSourceType.SEBI, "b", b"bbb")
        assert store.file_count() == 2

    def test_archive_old_version(self, store) -> None:
        store.store_raw_pdf(CrawlSourceType.RBI, "ver001", b"v1 content")
        store.archive_old_version(CrawlSourceType.RBI, "ver001", 1)
        ver_path = store.source_version_dir(CrawlSourceType.RBI) / "ver001" / "v1.pdf"
        assert ver_path.exists()
        assert ver_path.read_bytes() == b"v1 content"
