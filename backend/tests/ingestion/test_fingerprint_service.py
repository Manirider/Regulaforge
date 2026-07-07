from __future__ import annotations

from uuid import uuid4

import pytest
from regulaforge.ingestion.application.fingerprint_service import (
    DeduplicationService,
    FingerprintCalculator,
)
from regulaforge.ingestion.domain.models import DocumentFingerprint


class TestFingerprintCalculator:
    def setup_method(self) -> None:
        self.fp = FingerprintCalculator()

    def test_file_hash_consistency(self, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Hello World")
        h1 = self.fp.compute_file_hash(str(f))
        h2 = self.fp.compute_file_hash(str(f))
        assert h1 == h2
        assert len(h1) == 64

    def test_content_hash_normalization(self) -> None:
        text1 = "  Hello   World  "
        text2 = "Hello World"
        assert self.fp.compute_content_hash(text1) == self.fp.compute_content_hash(text2)

    def test_identical_texts_same_hash(self) -> None:
        text = "This is a regulatory circular about KYC norms for banks"
        h1 = self.fp.compute_content_hash(text)
        h2 = self.fp.compute_content_hash(text)
        assert h1 == h2

    def test_simhash_computation(self) -> None:
        text = "The Reserve Bank of India hereby publishes this master direction"
        simhash = self.fp.compute_simhash(text)
        assert simhash is not None
        assert isinstance(simhash, int)

    def test_simhash_similar_texts(self) -> None:
        text1 = "This is a circular about KYC compliance for all scheduled banks"
        text2 = "This is a circular about KYC compliance for all commercial banks"
        s1 = self.fp.compute_simhash(text1)
        s2 = self.fp.compute_simhash(text2)
        assert s1 is not None and s2 is not None
        sim = self.fp.similarity(s1, s2)
        assert sim > 0.5

    def test_simhash_different_texts(self) -> None:
        text1 = "Rules for foreign direct investment in insurance sector"
        text2 = "Guidelines on corporate governance for listed entities"
        s1 = self.fp.compute_simhash(text1)
        s2 = self.fp.compute_simhash(text2)
        sim = self.fp.similarity(s1, s2)
        assert sim < 0.8

    def test_hamming_distance(self) -> None:
        a = 0b1100
        b = 0b1010
        assert self.fp.hamming_distance(a, b) == 2

    def test_same_simhash_perfect_similarity(self) -> None:
        text = "Test document content"
        s1 = self.fp.compute_simhash(text)
        s2 = self.fp.compute_simhash(text)
        assert self.fp.similarity(s1, s2) == 1.0

    def test_empty_text_returns_none(self) -> None:
        assert self.fp.compute_simhash("") is None
        assert self.fp.compute_simhash("   ") is None

    def test_create_fingerprint_domain(self) -> None:
        from datetime import datetime, timezone

        from regulaforge.ingestion.domain.models import (
            CrawlSourceType,
            DocumentCategory,
            RegulatoryDocument,
        )
        doc = RegulatoryDocument(
            id=uuid4(),
            source_type=CrawlSourceType.RBI,
            external_id="RBI-FP-01",
            title="Test",
            category=DocumentCategory.CIRCULAR,
            url="https://rbi.org.in/test",
            published_date=datetime.now(timezone.utc),
            file_hash_sha256="abc123",
        )
        fp = self.fp.create_fingerprint(doc, "Sample regulatory text content")
        assert fp.document_id == doc.id
        assert fp.file_hash_sha256 == "abc123"
        assert fp.content_hash
        assert fp.num_tokens > 0


class TestDeduplicationService:
    def setup_method(self) -> None:
        self.fp = FingerprintCalculator()
        self.dedup = DeduplicationService(self.fp)

    @pytest.mark.asyncio
    async def test_exact_hash_duplicate(self) -> None:
        result = await self.dedup.is_duplicate_by_hash("abc123", {"abc123", "def456"})
        assert result is True

    @pytest.mark.asyncio
    async def test_new_hash_not_duplicate(self) -> None:
        result = await self.dedup.is_duplicate_by_hash("xyz789", {"abc123", "def456"})
        assert result is False

    @pytest.mark.asyncio
    async def test_content_duplicate_exact_match(self) -> None:
        text = "Regulatory document content here"
        existing_fps = [
            DocumentFingerprint(
                id=uuid4(),
                document_id=uuid4(),
                file_hash_sha256="h1",
                content_hash=self.fp.compute_content_hash(text),
                simhash=self.fp.compute_simhash(text),
                num_tokens=10,
            )
        ]
        result = await self.dedup.is_duplicate_by_content(text, existing_fps)
        assert result is True

    @pytest.mark.asyncio
    async def test_content_not_duplicate(self) -> None:
        existing_fps = [
            DocumentFingerprint(
                id=uuid4(),
                document_id=uuid4(),
                file_hash_sha256="h1",
                content_hash=self.fp.compute_content_hash("Some other text"),
                simhash=self.fp.compute_simhash("Some other text"),
                num_tokens=10,
            )
        ]
        result = await self.dedup.is_duplicate_by_content("Completely different", existing_fps)
        assert result is False
