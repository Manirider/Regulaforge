"""
Semantic chunking using embedding-based similarity to detect topic boundaries.

Sliding window over sentence embeddings identifies natural break points
where cosine similarity drops below a threshold.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from regulaforge.document_intelligence.domain.models import SemanticChunk


class ChunkOverlapMode(Enum):
    NONE = "none"
    SENTENCE = "sentence"
    CHUNK = "chunk"


@dataclass
class SemanticChunkingResult:
    chunks: list[SemanticChunk] = field(default_factory=list)
    num_chunks: int = 0
    overall_confidence: float = 0.0


class SemanticChunker(ABC):
    @abstractmethod
    async def chunk(
        self,
        text: str,
        **kwargs: Any,
    ) -> SemanticChunkingResult:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class SentenceTransformerChunker(SemanticChunker):
    """Semantic chunker using sentence-transformers for embedding similarity.

    Splits text into sentences, computes embeddings, and groups consecutive
    sentences where the cosine similarity between adjacent embeddings
    exceeds ``threshold``.

    Args:
        model_name: Sentence transformer model name.
        threshold: Similarity threshold for boundary detection
            (lower = more boundaries / smaller chunks).
        max_chunk_sentences: Maximum sentences per chunk before forcing a split.
        min_chunk_sentences: Minimum sentences per chunk.
        overlap_mode: How overlapping context between chunks is handled.
        overlap_window: Number of sentences (or characters) to overlap.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        threshold: float = 0.65,
        max_chunk_sentences: int = 20,
        min_chunk_sentences: int = 2,
        overlap_mode: ChunkOverlapMode = ChunkOverlapMode.NONE,
        overlap_window: int = 1,
    ) -> None:
        self._model_name = model_name
        self._threshold = threshold
        self._max_chunk_sentences = max_chunk_sentences
        self._min_chunk_sentences = min_chunk_sentences
        self._overlap_mode = overlap_mode
        self._overlap_window = overlap_window
        self._model = None
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return f"st:{self._model_name}"

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import sentence_transformers  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self._model_name)

    def _split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    async def chunk(
        self,
        text: str,
        **kwargs: Any,
    ) -> SemanticChunkingResult:
        sentences = self._split_sentences(text)
        if not sentences:
            return SemanticChunkingResult()

        self._load()

        embeddings = self._model.encode(sentences, convert_to_tensor=True)

        import torch

        break_indices: list[int] = [0]

        for i in range(1, len(sentences)):
            sim = float(torch.cosine_similarity(
                embeddings[i - 1].unsqueeze(0),
                embeddings[i].unsqueeze(0),
            ))

            sentences_in_chunk = i - break_indices[-1]

            if (sim < self._threshold and sentences_in_chunk >= self._min_chunk_sentences) or \
               sentences_in_chunk >= self._max_chunk_sentences:
                break_indices.append(i)

        break_indices.append(len(sentences))

        chunks: list[SemanticChunk] = []
        for j in range(len(break_indices) - 1):
            start = break_indices[j]
            end = break_indices[j + 1]

            if self._overlap_mode == ChunkOverlapMode.SENTENCE and j > 0:
                overlap_start = max(start - self._overlap_window, break_indices[j - 1])
                overlap_sentences = sentences[overlap_start:start]
            else:
                overlap_sentences = []

            chunk_sentences = sentences[start:end]
            chunk_text = " ".join(chunk_sentences)
            overlap_text = " ".join(overlap_sentences) if overlap_sentences else None

            text_before = " ".join(sentences[:start])
            char_start = len(text_before) + (1 if text_before else 0)
            char_end = char_start + len(chunk_text)

            chunks.append(
                SemanticChunk(
                    id=f"chunk-{j + 1}",
                    text=chunk_text,
                    page_number=kwargs.get("page_number", 0),
                    embedding=None,
                    confidence=0.85,
                    metadata={
                        "sentence_start": start,
                        "sentence_end": end,
                        "char_start": char_start,
                        "char_end": char_end,
                        "num_sentences": len(chunk_sentences),
                        "overlap": overlap_text[:100] if overlap_text else None,
                    },
                )
            )

        return SemanticChunkingResult(
            chunks=chunks,
            num_chunks=len(chunks),
            overall_confidence=0.85,
        )


class SentenceWindowChunker(SemanticChunker):
    """Simple sentence-window chunker with fixed-size windows (no embeddings).

    Useful when sentence-transformers is unavailable or for rapid prototyping.
    """

    def __init__(
        self,
        chunk_size: int = 10,
        overlap: int = 2,
    ) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._available: bool = True

    @property
    def name(self) -> str:
        return "sentence-window"

    async def is_available(self) -> bool:
        return True

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    async def chunk(
        self,
        text: str,
        **kwargs: Any,
    ) -> SemanticChunkingResult:
        sentences = self._split_sentences(text)
        if not sentences:
            return SemanticChunkingResult()

        chunks: list[SemanticChunk] = []
        step = self._chunk_size - self._overlap
        if step < 1:
            step = 1

        for i in range(0, len(sentences), step):
            end = min(i + self._chunk_size, len(sentences))
            chunk_sentences = sentences[i:end]
            chunk_text = " ".join(chunk_sentences)

            text_before = " ".join(sentences[:i])
            char_start = len(text_before) + (1 if text_before else 0)
            char_end = char_start + len(chunk_text)

            overlap_sentences = []
            if self._overlap > 0 and i > 0:
                overlap_start = max(i - self._overlap, 0)
                overlap_sentences = sentences[overlap_start:i]

            chunks.append(
                SemanticChunk(
                    id=f"chunk-{len(chunks) + 1}",
                    text=chunk_text,
                    page_number=kwargs.get("page_number", 0),
                    embedding=None,
                    confidence=0.7,
                    metadata={
                        "sentence_start": i,
                        "sentence_end": end,
                        "char_start": char_start,
                        "char_end": char_end,
                        "num_sentences": len(chunk_sentences),
                    },
                )
            )

            if end >= len(sentences):
                break

        return SemanticChunkingResult(
            chunks=chunks,
            num_chunks=len(chunks),
            overall_confidence=0.7,
        )
