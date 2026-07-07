"""Cross-encoder reranking — improves retrieval precision.

Reranks retrieved documents using a cross-encoder model for more
accurate relevance scoring than embedding-based similarity alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from regulaforge.config.logging import get_logger

from .retrievers import RetrievedDocument

logger = get_logger(__name__)


@dataclass
class RankedDocument:
    """A reranked document with cross-encoder relevance score."""

    document: RetrievedDocument
    original_score: float
    rerank_score: float
    position: int


class RerankingError(Exception):
    """Base exception for reranking operations."""


class CrossEncoderReranker:
    """Cross-encoder based reranker with fallback.

    Uses a cross-encoder model to compute passage-query relevance scores,
    then reranks documents accordingly. Falls back to original scores if
    the model is unavailable or inference fails.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        max_length: int = 512,
        batch_size: int = 32,
        device: str = "cpu",
        fallback_to_original: bool = True,
    ) -> None:
        self._model_name = model_name
        self._max_length = max_length
        self._batch_size = batch_size
        self._device = device
        self._fallback = fallback_to_original
        self._model: Any = None
        self._tokenizer: Any = None
        self._initialized = False

    def _lazy_init(self) -> None:
        """Lazy-load the cross-encoder model on first use."""
        if self._initialized:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self._model_name,
                max_length=self._max_length,
                device=self._device,
            )
            self._initialized = True
            logger.info("Loaded cross-encoder model: %s", self._model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed, cross-encoder unavailable",
            )
        except Exception as e:
            logger.error("Failed to load cross-encoder model: %s", str(e))

    async def rerank(
        self,
        query: str,
        documents: list[RetrievedDocument],
        *,
        top_k: Optional[int] = None,
        return_scores: bool = True,
    ) -> list[RankedDocument]:
        """Rerank documents by cross-encoder relevance to the query.

        Args:
            query: The search query.
            documents: Documents to rerank.
            top_k: Number of top results to return (None = all).
            return_scores: Include raw scores in output.

        Returns:
            Reranked list of RankedDocument objects.
        """
        if not documents:
            return []

        self._lazy_init()

        if not self._initialized or self._model is None:
            logger.warning("Cross-encoder unavailable, using original order")
            if self._fallback:
                return self._fallback_rerank(query, documents, top_k)
            raise RerankingError("Cross-encoder not available and fallback disabled")

        try:
            pairs = [[query, doc.text[:self._max_length]] for doc in documents]
            scores = self._model.predict(pairs, batch_size=self._batch_size)

            scored = [
                RankedDocument(
                    document=doc,
                    original_score=doc.score,
                    rerank_score=float(scores[i]) if return_scores else 0.0,
                    position=i,
                )
                for i, doc in enumerate(documents)
                if i < len(scores)
            ]

            scored.sort(key=lambda x: x.rerank_score, reverse=True)

            for pos, sd in enumerate(scored):
                sd.position = pos

            if top_k:
                scored = scored[:top_k]

            logger.info(
                "Reranked %d documents for query '%s'",
                len(scored), query[:60],
            )
            return scored

        except Exception as e:
            logger.error("Cross-encoder reranking failed: %s", str(e))
            if self._fallback:
                return self._fallback_rerank(query, documents, top_k)
            raise RerankingError(f"Reranking failed: {e}") from e

    def _fallback_rerank(
        self,
        query: str,
        documents: list[RetrievedDocument],
        top_k: Optional[int],
    ) -> list[RankedDocument]:
        scored = [
            RankedDocument(
                document=doc,
                original_score=doc.score,
                rerank_score=doc.score,
                position=i,
            )
            for i, doc in enumerate(documents)
        ]
        scored.sort(key=lambda x: x.rerank_score, reverse=True)
        for pos, sd in enumerate(scored):
            sd.position = pos
        return scored[:top_k] if top_k else scored
