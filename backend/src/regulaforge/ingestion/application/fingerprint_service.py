from __future__ import annotations

import hashlib
from uuid import uuid4

from regulaforge.ingestion.domain.models import DocumentFingerprint, RegulatoryDocument


class FingerprintCalculator:
    SHINGLE_SIZE = 4
    HASH_BITS = 64

    def compute_file_hash(self, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _tokenize(self, text: str) -> list[str]:
        return text.strip().split()

    def _shingles(self, tokens: list[str]) -> list[str]:
        if len(tokens) < self.SHINGLE_SIZE:
            return [" ".join(tokens)] if tokens else []
        return [" ".join(tokens[i : i + self.SHINGLE_SIZE]) for i in range(len(tokens) - self.SHINGLE_SIZE + 1)]

    def _hash_shingle(self, shingle: str) -> int:
        return int.from_bytes(
            hashlib.md5(shingle.encode("utf-8")).digest()[:8], byteorder="big",
        )

    def compute_simhash(self, text: str) -> int | None:
        tokens = self._tokenize(text)
        if not tokens:
            return None
        shingles = self._shingles(tokens)
        if not shingles:
            return None
        v = [0] * self.HASH_BITS
        for shingle in shingles:
            h = self._hash_shingle(shingle)
            for i in range(self.HASH_BITS):
                mask = 1 << i
                if h & mask:
                    v[i] += 1
                else:
                    v[i] -= 1
        fingerprint = 0
        for i in range(self.HASH_BITS):
            if v[i] > 0:
                fingerprint |= 1 << i
        return fingerprint

    def compute_content_hash(self, text: str) -> str:
        norm = " ".join(text.strip().split())
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def hamming_distance(self, a: int, b: int) -> int:
        return (a ^ b).bit_count()

    def similarity(self, a: int, b: int) -> float:
        return 1.0 - self.hamming_distance(a, b) / self.HASH_BITS

    def create_fingerprint(self, doc: RegulatoryDocument, text: str) -> DocumentFingerprint:
        content_hash = self.compute_content_hash(text)
        simhash = self.compute_simhash(text)
        num_tokens = len(self._tokenize(text))
        return DocumentFingerprint(
            id=uuid4(),
            document_id=doc.id,
            file_hash_sha256=doc.file_hash_sha256 or "",
            content_hash=content_hash,
            simhash=simhash,
            num_tokens=num_tokens,
        )


class DeduplicationService:
    def __init__(
        self,
        fingerprint_calculator: FingerprintCalculator,
    ) -> None:
        self._fp = fingerprint_calculator

    async def is_duplicate_by_hash(
        self,
        file_hash: str,
        existing_hashes: set[str],
    ) -> bool:
        return file_hash in existing_hashes

    async def is_duplicate_by_content(
        self,
        new_text: str,
        existing_fingerprints: list[DocumentFingerprint],
        threshold: float = 0.95,
    ) -> bool:
        new_content_hash = self._fp.compute_content_hash(new_text)
        new_simhash = self._fp.compute_simhash(new_text)
        for ef in existing_fingerprints:
            if ef.content_hash == new_content_hash:
                return True
            if new_simhash is not None and ef.simhash is not None:  # noqa: SIM102
                if self._fp.similarity(new_simhash, ef.simhash) >= threshold:
                    return True
        return False
