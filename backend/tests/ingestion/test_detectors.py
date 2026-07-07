from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from regulaforge.ingestion.detectors.duplicate import DuplicateDetector, DuplicateLevel
from regulaforge.ingestion.detectors.fingerprint import (
    Fingerprint,
    FingerprintDetector,
    SimHashComparator,
)
from regulaforge.ingestion.detectors.hash_verifier import HashAlgorithm, HashVerifier
from regulaforge.ingestion.detectors.version import (
    ChangeType,
    DocumentSnapshot,
    VersionDetector,
)
from regulaforge.ingestion.domain.models import DocumentFingerprint


class TestSimHashComparator:
    def setup_method(self) -> None:
        self.comparator = SimHashComparator()

    def test_compute_returns_hex_string(self) -> None:
        result = self.comparator.compute("test text")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_identical_texts_same_hash(self) -> None:
        text = "regulatory circular about KYC compliance"
        h1 = self.comparator.compute(text)
        h2 = self.comparator.compute(text)
        assert h1 == h2

    def test_similar_texts_near_distance(self) -> None:
        t1 = "Guidelines on corporate governance for listed entities"
        t2 = "Guidelines on corporate governance for all entities"
        h1 = self.comparator.compute(t1)
        h2 = self.comparator.compute(t2)
        dist = SimHashComparator.hamming_distance(h1, h2)
        assert dist < 20

    def test_different_texts_far_distance(self) -> None:
        t1 = "Rules for foreign direct investment in insurance"
        t2 = "Procedure for filing annual returns by NBFCs"
        h1 = self.comparator.compute(t1)
        h2 = self.comparator.compute(t2)
        dist = SimHashComparator.hamming_distance(h1, h2)
        assert dist > 5

    def test_hamming_distance_identical(self) -> None:
        assert SimHashComparator.hamming_distance("abcd1234abcd1234", "abcd1234abcd1234") == 0

    def test_similarity_identical(self) -> None:
        sim = SimHashComparator.similarity("abcd1234abcd1234", "abcd1234abcd1234")
        assert sim == 1.0

    def test_similarity_range(self) -> None:
        h1 = self.comparator.compute("AAAA")
        h2 = self.comparator.compute("BBBB")
        sim = SimHashComparator.similarity(h1, h2)
        assert 0.0 <= sim <= 1.0

    def test_empty_text(self) -> None:
        result = self.comparator.compute("")
        assert result == "0" * 16

    def test_invalid_hash_raises(self) -> None:
        with pytest.raises(Exception):
            SimHashComparator.hamming_distance("invalid", "0000")


class TestFingerprintDetector:
    def setup_method(self) -> None:
        self.detector = FingerprintDetector()

    def test_compute_file_hash_consistency(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"PDF content here")
        h1 = self.detector.compute_file_hash(f)
        h2 = self.detector.compute_file_hash(f)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_files_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.pdf"
        f2 = tmp_path / "b.pdf"
        f1.write_bytes(b"content a")
        f2.write_bytes(b"content b")
        assert self.detector.compute_file_hash(f1) != self.detector.compute_file_hash(f2)

    def test_compute_content_hash(self) -> None:
        h = self.detector.compute_content_hash("test content")
        assert len(h) == 64
        assert isinstance(h, str)

    def test_compute_fingerprint(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_bytes(b"regulatory document content")
        fp = self.detector.compute_fingerprint(f, "regulatory document content")
        assert isinstance(fp, Fingerprint)
        assert len(fp.file_hash) == 64
        assert len(fp.content_hash) == 64
        assert len(fp.simhash) == 16
        assert fp.hash_algorithm == "sha256"

    def test_fingerprint_to_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_bytes(b"content")
        fp = self.detector.compute_fingerprint(f, "content")
        d = fp.to_dict()
        assert d["file_hash"] == fp.file_hash
        assert d["content_hash"] == fp.content_hash
        assert d["simhash"] == fp.simhash

    def test_md5_algorithm(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"test")
        fp = self.detector.compute_fingerprint(f, "test", hash_algorithm="md5")
        assert len(fp.file_hash) == 32


class TestDuplicateDetector:
    def setup_method(self) -> None:
        self.detector = DuplicateDetector(simhash_threshold=0.85)

    def _make_fingerprint(
        self,
        file_hash: str = "h1",
        content_hash: str = "ch1",
        simhash: str = "0000000000000000",
    ) -> DocumentFingerprint:
        return DocumentFingerprint(
            id=uuid4(),
            document_id=uuid4(),
            file_hash_sha256=file_hash,
            content_hash=content_hash,
            simhash=int(simhash, 16) if simhash else None,
            num_tokens=10,
        )

    @pytest.mark.asyncio
    async def test_exact_file_duplicate(self, tmp_path: Path) -> None:
        import hashlib
        f = tmp_path / "doc.txt"
        f.write_bytes(b"exact content")
        file_hash = hashlib.sha256(b"exact content").hexdigest()
        existing = self._make_fingerprint(file_hash=file_hash)
        result = await self.detector.check_duplicate(
            filepath=f,
            content="exact content",
            existing_fingerprints=[existing],
        )
        assert result.is_duplicate
        assert result.level == DuplicateLevel.EXACT_FILE

    @pytest.mark.asyncio
    async def test_exact_content_duplicate(self, tmp_path: Path) -> None:
        import hashlib
        content = "exact content text"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        f = tmp_path / "doc.txt"
        f.write_bytes(content.encode())
        existing = self._make_fingerprint(file_hash="otherhash", content_hash=content_hash)
        result = await self.detector.check_duplicate(
            filepath=f,
            content=content,
            existing_fingerprints=[existing],
        )
        assert result.is_duplicate
        assert result.level == DuplicateLevel.EXACT_CONTENT

    @pytest.mark.asyncio
    async def test_not_duplicate(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"new content")
        existing = self._make_fingerprint(
            file_hash="oldhash",
            content_hash="oldcontent",
        )
        result = await self.detector.check_duplicate(
            filepath=f,
            content="new content",
            existing_fingerprints=[existing],
        )
        assert not result.is_duplicate
        assert result.level == DuplicateLevel.NOT_DUPLICATE

    @pytest.mark.asyncio
    async def test_empty_existing_list(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"content")
        result = await self.detector.check_duplicate(
            filepath=f,
            content="content",
            existing_fingerprints=[],
        )
        assert not result.is_duplicate
        assert result.level == DuplicateLevel.NOT_DUPLICATE

    @pytest.mark.asyncio
    async def test_near_duplicate_simhash(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"A similar document about KYC compliance for banks")
        content = "A similar document about KYC compliance for banks"

        from regulaforge.ingestion.detectors.fingerprint import SimHashComparator
        simhash_comp = SimHashComparator()
        simhash_hex = simhash_comp.compute(content)

        existing = self._make_fingerprint(
            file_hash="different",
            content_hash="different_content",
            simhash=simhash_hex,
        )
        result = await self.detector.check_duplicate(
            filepath=f,
            content=content,
            existing_fingerprints=[existing],
        )
        assert result.is_duplicate
        assert result.level == DuplicateLevel.NEAR_DUPLICATE
        assert result.similarity_score >= 0.85

    @pytest.mark.asyncio
    async def test_below_threshold_not_duplicate(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"Completely unrelated content about tax law")
        content = "Completely unrelated content about tax law"

        existing = self._make_fingerprint(
            file_hash="different",
            content_hash="different_content",
            simhash="ffffffffffffffff",
        )
        result = await self.detector.check_duplicate(
            filepath=f,
            content=content,
            existing_fingerprints=[existing],
        )
        assert not result.is_duplicate
        assert result.level == DuplicateLevel.NOT_DUPLICATE

    @pytest.mark.asyncio
    async def test_first_match_short_circuits(self, tmp_path: Path) -> None:
        import hashlib
        f = tmp_path / "doc.txt"
        f.write_bytes(b"content")
        file_hash = hashlib.sha256(b"content").hexdigest()
        existing_file = self._make_fingerprint(file_hash=file_hash)
        existing_content = self._make_fingerprint(file_hash="other", content_hash="content")
        result = await self.detector.check_duplicate(
            filepath=f,
            content="other content",
            existing_fingerprints=[existing_file, existing_content],
        )
        assert result.is_duplicate
        assert result.level == DuplicateLevel.EXACT_FILE


class TestVersionDetector:
    def setup_method(self) -> None:
        self.detector = VersionDetector()

    def _snapshot(
        self,
        file_hash: str = "abc",
        content_hash: str = "def",
        title: str = "Doc",
        category: str = "circular",
        source_type: str = "rbi",
    ) -> DocumentSnapshot:
        return DocumentSnapshot(
            external_id="ext-1",
            title=title,
            file_hash=file_hash,
            content_hash=content_hash,
            category=category,
            source_type=source_type,
            publication_date="2024-01-01",
            file_size_bytes=1000,
        )

    def test_new_document(self) -> None:
        current = self._snapshot()
        result = self.detector.detect_change(current, None)
        assert result.change_type == ChangeType.NEW_DOCUMENT

    def test_no_change(self) -> None:
        snap = self._snapshot()
        result = self.detector.detect_change(snap, snap)
        assert result.change_type == ChangeType.NO_CHANGE

    def test_content_changed(self) -> None:
        current = self._snapshot(file_hash="new_hash", content_hash="new_content")
        previous = self._snapshot(file_hash="old_hash", content_hash="old_content")
        result = self.detector.detect_change(current, previous)
        assert result.change_type == ChangeType.CONTENT_CHANGED
        assert result.previous_hash == "old_hash"
        assert result.current_hash == "new_hash"

    def test_metadata_changed(self) -> None:
        current = self._snapshot(file_hash="same", content_hash="same", title="New Title")
        previous = self._snapshot(file_hash="same", content_hash="same", title="Old Title")
        result = self.detector.detect_change(current, previous)
        assert result.change_type == ChangeType.METADATA_CHANGED
        assert "title" in result.changed_fields


class TestHashVerifier:
    def setup_method(self) -> None:
        self.verifier = HashVerifier()

    def test_verify_file_success(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"content")
        h = self.verifier.compute_file_hash(f)
        assert self.verifier.verify_file(f, h) is True

    def test_verify_file_failure(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"content")
        assert self.verifier.verify_file(f, "wronghash") is False

    def test_verify_content_success(self) -> None:
        h = self.verifier.compute_content_hash("hello")
        assert self.verifier.verify_content("hello", h) is True

    def test_compute_hash_bytes(self) -> None:
        h = HashVerifier.compute_hash(b"data")
        assert len(h) == 64

    def test_md5_algorithm(self, tmp_path: Path) -> None:
        v = HashVerifier(algorithm=HashAlgorithm.MD5)
        f = tmp_path / "test.txt"
        f.write_bytes(b"test")
        h = v.compute_file_hash(f)
        assert len(h) == 32

    def test_different_algorithms_different_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_bytes(b"test")
        sha256 = HashVerifier(HashAlgorithm.SHA256).compute_file_hash(f)
        md5 = HashVerifier(HashAlgorithm.MD5).compute_file_hash(f)
        assert sha256 != md5

    def test_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        assert self.verifier.verify_file(tmp_path / "nonexistent.pdf", "hash") is False

    def test_empty_content_hash(self) -> None:
        h = self.verifier.compute_content_hash("")
        assert len(h) == 64

    def test_compute_hash_bytes_consistency(self) -> None:
        h1 = HashVerifier.compute_hash(b"hello world")
        h2 = HashVerifier.compute_hash(b"hello world")
        assert h1 == h2
