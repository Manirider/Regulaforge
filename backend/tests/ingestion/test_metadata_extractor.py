from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from regulaforge.ingestion.domain.models import (
    CrawlSourceType,
    DocumentCategory,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.infrastructure.extractors.metadata_extractor import MetadataExtractor


class TestMetadataExtractor:
    @pytest.fixture
    def extractor(self) -> MetadataExtractor:
        return MetadataExtractor()

    def test_extract_from_text_file(self, extractor, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Hello World")
        meta = extractor.extract_from_path(str(f))
        assert meta["file_name"] == "test.txt"
        assert meta["file_extension"] == ".txt"
        assert meta["file_size_bytes"] == 11

    def test_extract_from_pdf_no_pypdf2(self, extractor, tmp_path) -> None:
        f = tmp_path / "test.pdf"
        f.write_text("%PDF-1.4 fake content")
        meta = extractor.extract_from_path(str(f))
        assert meta["file_name"] == "test.pdf"
        assert "file_size_bytes" in meta

    def test_build_document_metadata(self, extractor, tmp_path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_text("content")
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.SEBI,
            external_id="SEBI-META-001",
            title="Test Meta",
            category=DocumentCategory.CIRCULAR,
            url="https://sebi.gov.in/meta.pdf",
            published_date=datetime(2024, 3, 15, tzinfo=timezone.utc),
            status=DocumentStatus.DOWNLOADED,
            file_hash_sha256="abc",
        )
        meta = extractor.build_document_metadata(doc, str(f), text="Some extracted text")
        assert meta["title"] == "Test Meta"
        assert meta["source_type"] == "sebi"
        assert meta["document_url"] == "https://sebi.gov.in/meta.pdf"
        assert meta["text_length"] == 19
        assert meta["word_count"] == 3

    def test_save_and_load_metadata(self, extractor, tmp_path) -> None:
        meta = {"key": "value", "number": 42}
        target = tmp_path / "meta.json"
        extractor.save_metadata(meta, target)
        assert target.exists()
        loaded = extractor.load_metadata(target)
        assert loaded == meta

    def test_load_nonexistent_metadata(self, extractor) -> None:
        assert extractor.load_metadata(Path("/nonexistent/meta.json")) is None
