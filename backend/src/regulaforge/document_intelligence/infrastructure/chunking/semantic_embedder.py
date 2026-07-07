from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class SemanticEmbedder:
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._model = None

    async def load(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name, device=self._device)
            logger.info("Embedding model loaded: %s", self._model_name)
        except ImportError:
            logger.warning("sentence-transformers not available for embeddings")
        except Exception as exc:
            logger.warning("Failed to load embedding model: %s", exc)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            await self.load()
        if self._model is None:
            return [[0.0]] * len(texts)

        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return [e.tolist() for e in embeddings]
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return [[0.0]] * len(texts)

    async def embed_single(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0] if results else []

    async def compute_similarity(self, a: list[float], b: list[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
