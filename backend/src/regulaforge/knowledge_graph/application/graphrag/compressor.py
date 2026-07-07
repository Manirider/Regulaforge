"""Context compression — reduces retrieved context to the essential.

Supports extractive (relevance-based truncation) and abstractive
(LLM-based summarization) compression modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from regulaforge.config.logging import get_logger

from .reranker import RankedDocument

logger = get_logger(__name__)


@dataclass
class CompressedContext:
    """Compressed context with original and compressed versions."""

    original_chunks: list[dict[str, Any]]
    compressed_text: str
    compression_ratio: float
    mode: str
    token_count_original: int
    token_count_compressed: int
    dropped_chunks: list[dict[str, Any]] = field(default_factory=list)


class CompressionError(Exception):
    """Base exception for context compression."""


class ContextCompressor:
    """Compresses retrieved context to fit within token limits while preserving key information.

    Two modes:
    - extractive: Drops low-relevance chunks, keeps top-k by score.
    - abstractive: Uses LLM to summarize the context into a concise form.
    """

    def __init__(
        self,
        llm_provider: Optional[Any] = None,
        max_tokens: int = 4096,
        compression_mode: str = "extractive",
        min_chunks: int = 1,
    ) -> None:
        self._llm_provider = llm_provider
        self._max_tokens = max_tokens
        self._mode = compression_mode
        self._min_chunks = min_chunks

    async def compress(
        self,
        query: str,
        documents: list[RankedDocument],
        *,
        mode: Optional[str] = None,
    ) -> CompressedContext:
        """Compress retrieved documents for the given query.

        Args:
            query: The original search query.
            documents: Ranked documents to compress.
            mode: Override default compression mode ('extractive' or 'abstractive').

        Returns:
            CompressedContext with compressed text and metadata.
        """
        effective_mode = mode or self._mode

        original_chunks = [
            {
                "id": d.document.id,
                "text": d.document.text[:1000],
                "score": d.rerank_score,
                "source": d.document.source,
                "title": d.document.title,
                "node_id": d.document.node_id,
            }
            for d in documents
        ]

        original_text = "\n\n".join(
            f"[{i + 1}] {c['title']}: {c['text']}"
            for i, c in enumerate(original_chunks)
        )

        original_tokens = 0 if not original_chunks else self._estimate_tokens(original_text)

        if effective_mode == "extractive":
            return await self._compress_extractive(
                query, documents, original_chunks, original_text, original_tokens,
            )
        elif effective_mode == "abstractive":
            return await self._compress_abstractive(
                query, original_chunks, original_text, original_tokens,
            )
        else:
            logger.warning("Unknown compression mode '%s', using extractive", effective_mode)
            return await self._compress_extractive(
                query, documents, original_chunks, original_text, original_tokens,
            )

    async def _compress_extractive(
        self,
        query: str,
        documents: list[RankedDocument],
        original_chunks: list[dict[str, Any]],
        original_text: str,
        original_tokens: int,
    ) -> CompressedContext:
        kept: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []
        token_count = 0

        for chunk in original_chunks:
            chunk_tokens = self._estimate_tokens(chunk["text"])
            if token_count + chunk_tokens <= self._max_tokens or len(kept) < self._min_chunks:
                kept.append(chunk)
                token_count += chunk_tokens
            else:
                dropped.append(chunk)

        compressed_text = "\n\n".join(
            f"[{i + 1}] {c['title']}: {c['text']}"
            for i, c in enumerate(kept)
        )

        logger.info(
            "Extractive compression: kept=%d dropped=%d ratio=%.2f",
            len(kept), len(dropped),
            token_count / max(original_tokens, 1),
        )

        return CompressedContext(
            original_chunks=original_chunks,
            compressed_text=compressed_text,
            compression_ratio=token_count / max(original_tokens, 1),
            mode="extractive",
            token_count_original=original_tokens,
            token_count_compressed=token_count,
            dropped_chunks=dropped,
        )

    async def _compress_abstractive(
        self,
        query: str,
        original_chunks: list[dict[str, Any]],
        original_text: str,
        original_tokens: int,
    ) -> CompressedContext:
        if not self._llm_provider:
            logger.warning("No LLM provider for abstractive compression, using extractive")
            return await self._compress_extractive(
                query,
                [
                    RankedDocument(
                        document=chunk,
                        original_score=chunk["score"],
                        rerank_score=chunk["score"],
                        position=i,
                    )
                    for i, chunk in enumerate(original_chunks)
                ],
                original_chunks,
                original_text,
                original_tokens,
            )

        try:
            prompt = (
                "Compress the following retrieved context into a concise summary "
                "that preserves all key information relevant to answering the query. "
                f"\n\nQuery: {query}\n\nContext:\n{original_text}\n\n"
                "Compressed summary:"
            )
            compressed = await self._llm_provider.generate(prompt)
            compressed_tokens = self._estimate_tokens(compressed)

            logger.info(
                "Abstractive compression: ratio=%.2f",
                compressed_tokens / max(original_tokens, 1),
            )

            return CompressedContext(
                original_chunks=original_chunks,
                compressed_text=compressed,
                compression_ratio=compressed_tokens / max(original_tokens, 1),
                mode="abstractive",
                token_count_original=original_tokens,
                token_count_compressed=compressed_tokens,
                dropped_chunks=[],
            )
        except Exception as e:
            logger.error("Abstractive compression failed: %s", str(e))
            return await self._compress_extractive(
                query,
                [
                    RankedDocument(
                        document=chunk,
                        original_score=chunk["score"],
                        rerank_score=chunk["score"],
                        position=i,
                    )
                    for i, chunk in enumerate(original_chunks)
                ],
                original_chunks,
                original_text,
                original_tokens,
            )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)
