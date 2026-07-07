from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CrossEncoder:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self._model: Any = None

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder as SECrossEncoder

            self._model = SECrossEncoder(
                self.model_name,
                device=self.device,
                max_length=self.max_length,
            )
            logger.info(
                "Loaded cross-encoder model %s on %s",
                self.model_name,
                self.device,
            )
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; using fallback scoring"
            )
            self._model = None

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        self._lazy_load()

        if not candidates:
            return []

        texts = [
            self._truncate(c["text"]) if self._model else c["text"]
            for c in candidates
        ]

        if self._model is not None:
            scores = self._model.predict([(query, t) for t in texts])
            scores = scores.tolist() if hasattr(scores, "tolist") else list(scores)
        else:
            scores = self._fallback_score(query, texts)

        reranked = []
        for i, cand in enumerate(candidates):
            reranked.append({
                "id": cand["id"],
                "score": float(scores[i]),
                "original_rank": i,
            })

        reranked.sort(key=lambda x: x["score"], reverse=True)

        if top_k is not None:
            reranked = reranked[:top_k]

        return reranked

    def _fallback_score(
        self, query: str, texts: list[str]
    ) -> list[float]:
        query_terms = set(query.lower().split())
        scores = []
        for text in texts:
            text_terms = set(text.lower().split())
            if not query_terms:
                scores.append(0.0)
                continue
            overlap = len(query_terms & text_terms)
            score = overlap / len(query_terms)
            scores.append(score)
        return scores

    def _truncate(self, text: str) -> str:
        words = text.split()
        if len(words) > self.max_length:
            return " ".join(words[: self.max_length])
        return text
