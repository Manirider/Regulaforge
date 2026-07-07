from __future__ import annotations

import logging
from typing import Any

from regulaforge.graphrag.domain.models import ChunkNode, EntityNode

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    def __init__(
        self,
        embedding_model: Any,
        qdrant_client: Any,
        batch_size: int = 64,
    ) -> None:
        self.embedder = embedding_model
        self.qdrant = qdrant_client
        self.batch_size = batch_size

    async def embed_and_store_chunks(
        self,
        chunks: list[ChunkNode],
    ) -> int:
        total = 0
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            texts = [c.text for c in batch]
            vectors = self.embedder.embed(texts)

            points = []
            for j, chunk in enumerate(batch):
                points.append({
                    "id": chunk.id,
                    "vector": vectors[j],
                    "payload": {
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "heading": chunk.heading,
                        "text": chunk.text[:500],
                        "type": "chunk",
                    },
                })

            await self.qdrant.upsert_points(points)
            total += len(batch)

        logger.info("Stored %d chunk embeddings in Qdrant", total)
        return total

    async def embed_and_store_entities(
        self,
        entities: list[EntityNode],
    ) -> int:
        total = 0
        for i in range(0, len(entities), self.batch_size):
            batch = entities[i : i + self.batch_size]
            texts = [e.name + (" " + e.description if e.description else "") for e in batch]
            vectors = self.embedder.embed(texts)

            points = []
            for j, entity in enumerate(batch):
                points.append({
                    "id": entity.id,
                    "vector": vectors[j],
                    "payload": {
                        "name": entity.name,
                        "category": entity.category.value,
                        "description": entity.description,
                        "type": "entity",
                    },
                })

            await self.qdrant.upsert_points(points)
            total += len(batch)

        logger.info("Stored %d entity embeddings in Qdrant", total)
        return total

    async def embed_query(self, query: str) -> list[float]:
        result: list[float] = self.embedder.embed_query(query)
        return result
