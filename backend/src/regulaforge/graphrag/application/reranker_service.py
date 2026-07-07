from __future__ import annotations

import logging
from typing import Any

from regulaforge.graphrag.domain.models import RankedResult, RetrievalResult

logger = logging.getLogger(__name__)


class RerankerService:
    def __init__(
        self,
        cross_encoder: Any,
        top_k: int = 20,
        min_score: float = 0.0,
    ) -> None:
        self.cross_encoder = cross_encoder
        self.top_k = top_k
        self.min_score = min_score

    async def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RankedResult]:
        if not results:
            return []

        candidates = [
            {"id": r.chunk_id, "text": r.text}
            for r in results
        ]

        scored = self.cross_encoder.rerank(query, candidates, top_k=None)

        score_map: dict[str, float] = {s["id"]: s["score"] for s in scored}

        reranked = []
        for _i, r in enumerate(results):
            rerank_score = score_map.get(r.chunk_id, 0.0)
            if rerank_score < self.min_score:
                continue
            reranked.append(
                RankedResult(
                    result=r,
                    rank=0,
                    rerank_score=rerank_score,
                    original_score=r.score,
                )
            )

        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        for rank, rr in enumerate(reranked):
            rr.rank = rank + 1

        final = reranked[:self.top_k]
        logger.info(
            "Reranked %d candidates -> %d results (min_score=%.2f)",
            len(results),
            len(final),
            self.min_score,
        )
        return final
