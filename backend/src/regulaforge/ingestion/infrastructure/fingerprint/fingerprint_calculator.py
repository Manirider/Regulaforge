from __future__ import annotations

import hashlib


class ContentFingerprinter:
    SHINGLE_SIZE = 4
    HASH_BITS = 64

    def compute_file_hash(self, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def compute_content_hash(self, text: str) -> str:
        norm = " ".join(text.strip().split())
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def _tokenize(self, text: str) -> list[str]:
        return [t for t in text.strip().split() if len(t) > 1]

    def _shingles(self, tokens: list[str]) -> list[str]:
        if len(tokens) < self.SHINGLE_SIZE:
            return [" ".join(tokens)] if tokens else []
        return [
            " ".join(tokens[i : i + self.SHINGLE_SIZE])
            for i in range(len(tokens) - self.SHINGLE_SIZE + 1)
        ]

    def _hash_shingle(self, shingle: str) -> int:
        return int.from_bytes(
            hashlib.md5(shingle.encode("utf-8")).digest()[:8],
            byteorder="big",
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
                if h & (1 << i):
                    v[i] += 1
                else:
                    v[i] -= 1

        fingerprint = 0
        for i in range(self.HASH_BITS):
            if v[i] > 0:
                fingerprint |= 1 << i
        return fingerprint

    def hamming_distance(self, a: int, b: int) -> int:
        return (a ^ b).bit_count()

    def similarity(self, a: int | None, b: int | None) -> float:
        if a is None or b is None:
            return 0.0
        if a == b:
            return 1.0
        return 1.0 - self.hamming_distance(a, b) / self.HASH_BITS

    def is_similar(self, a: int | None, b: int | None, threshold: float = 0.95) -> bool:
        return self.similarity(a, b) >= threshold
