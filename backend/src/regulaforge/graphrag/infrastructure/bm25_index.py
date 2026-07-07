from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._documents: list[dict[str, Any]] = []
        self._doc_freqs: list[Counter[str]] = []
        self._idf: dict[str, float] = {}
        self._avg_doc_length: float = 0.0
        self._total_docs: int = 0
        self._built = False

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())

    def add_document(self, doc_id: str, text: str, metadata: Optional[dict[str, Any]] = None) -> None:
        self._documents.append({
            "id": doc_id,
            "text": text,
            "metadata": metadata or {},
        })

    def add_documents(self, docs: list[dict[str, Any]]) -> None:
        for doc in docs:
            self.add_document(doc["id"], doc["text"], doc.get("metadata"))

    def build(self) -> None:
        if not self._documents:
            self._built = True
            return

        total_terms = 0
        doc_freq: Counter[str] = Counter()

        self._doc_freqs = []
        for doc in self._documents:
            tokens = self._tokenize(doc["text"])
            freq = Counter(tokens)
            self._doc_freqs.append(freq)
            total_terms += len(tokens)
            for term in set(tokens):
                doc_freq[term] += 1

        self._total_docs = len(self._documents)
        self._avg_doc_length = total_terms / self._total_docs if self._total_docs > 0 else 0

        for term, df in doc_freq.items():
            self._idf[term] = math.log(
                1 + (self._total_docs - df + 0.5) / (df + 0.5)
            )

        self._built = True
        logger.info(
            "BM25 index built: %d docs, %d terms, avg_len=%.1f",
            self._total_docs,
            len(self._idf),
            self._avg_doc_length,
        )

    def search(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        if not self._built:
            self.build()

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: list[float] = []
        for _i, doc_freq in enumerate(self._doc_freqs):
            doc_length = sum(doc_freq.values())
            score = 0.0
            for qtok in query_tokens:
                if qtok not in self._idf:
                    continue
                tf = doc_freq.get(qtok, 0)
                idf = self._idf[qtok]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * (doc_length / self._avg_doc_length)
                )
                score += idf * (numerator / denominator) if denominator > 0 else 0
            scores.append(score)

        scored: list[dict[str, Any]] = [
            {"id": self._documents[i]["id"], "score": scores[i], "metadata": self._documents[i].get("metadata", {})}
            for i in range(len(self._documents))
        ]
        scored.sort(key=lambda x: float(x["score"]), reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        self._documents.clear()
        self._doc_freqs.clear()
        self._idf.clear()
        self._avg_doc_length = 0.0
        self._total_docs = 0
        self._built = False
