from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingModel:
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        max_retries: int = 3,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_retries = max_retries
        self._model: Any = None

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name, device=self.device
            )
            logger.info(
                "Loaded embedding model %s on %s (dim=%d)",
                self.model_name,
                self.device,
                self._model.get_sentence_embedding_dimension(),
            )
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; using fallback embedding"
            )
            self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._lazy_load()
        if self._model is None:
            return self._fallback_embed(texts)
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return [e.tolist() for e in embeddings]

    def embed_query(self, text: str) -> list[float]:
        self._lazy_load()
        if self._model is None:
            return self._fallback_embed([text])[0]
        embedding = self._model.encode(text, show_progress_bar=False)
        result: list[float] = embedding.tolist()
        return result

    def _fallback_embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib

        dim = 384
        result = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            vec = [int(h[i % len(h)]) / 255.0 for i in range(dim)]
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            result.append(vec)
        return result

    @property
    def dimension(self) -> int:
        self._lazy_load()
        if self._model is not None:
            dim: int = self._model.get_sentence_embedding_dimension()
            return dim
        return 384
