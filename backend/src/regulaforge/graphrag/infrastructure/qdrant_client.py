from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QdrantClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "regulaforge_chunks",
        prefer_grpc: bool = False,
        max_retries: int = 3,
    ) -> None:
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.prefer_grpc = prefer_grpc
        self.max_retries = max_retries
        self._client: Any = None
        self._collection_ready = False

    async def connect(self) -> None:
        from qdrant_client import AsyncQdrantClient

        self._client = AsyncQdrantClient(
            host=self.host,
            port=self.port,
            prefer_grpc=self.prefer_grpc,
        )
        await self._ensure_collection(384)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def _ensure_collection(self, vector_size: int) -> None:
        collections = await self._client.get_collections()
        exists = any(
            c.name == self.collection_name for c in collections.collections
        )
        if not exists:
            from qdrant_client.models import (
                Distance,
                HnswConfigDiff,
                VectorParams,
            )

            await self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size, distance=Distance.COSINE
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=200,
                ),
            )
            logger.info("Created Qdrant collection %s", self.collection_name)
        self._collection_ready = True

    async def upsert_points(
        self,
        points: list[dict[str, Any]],
    ) -> None:
        if not self._client or not self._collection_ready:
            raise RuntimeError("Qdrant client not connected")

        from qdrant_client.models import Batch

        ids = [p["id"] for p in points]
        vectors = [p["vector"] for p in points]
        payloads = [p.get("payload", {}) for p in points]

        await self._client.upsert(
            collection_name=self.collection_name,
            points=Batch(ids=ids, vectors=vectors, payloads=payloads),
        )

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        if not self._client or not self._collection_ready:
            raise RuntimeError("Qdrant client not connected")

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = None
        if filter_conditions:
            conditions = []
            for field, value in filter_conditions.items():
                conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value),
                    )
                )
            if conditions:
                query_filter = Filter(must=conditions)

        results = await self._client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload or {},
                "version": r.version,
            }
            for r in results
        ]

    async def search_by_payload(
        self,
        field: str,
        value: Any,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if not self._client or not self._collection_ready:
            raise RuntimeError("Qdrant client not connected")

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        results = await self._client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value),
                    )
                ]
            ),
            limit=limit,
        )
        points = results[0] if isinstance(results, tuple) else results
        return [
            {
                "id": p.id,
                "score": 1.0,
                "payload": p.payload or {},
            }
            for p in points
        ]

    async def delete_points(self, point_ids: list[str]) -> None:
        if not self._client or not self._collection_ready:
            raise RuntimeError("Qdrant client not connected")
        await self._client.delete(
            collection_name=self.collection_name,
            points_selector=point_ids,
        )

    async def collection_info(self) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("Qdrant client not connected")
        info = await self._client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "status": str(info.status),
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
        }
