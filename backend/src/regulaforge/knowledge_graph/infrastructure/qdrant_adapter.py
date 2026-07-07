"""Qdrant vector store adapter — production-grade vector search.

Provides dense vector storage, payload filtering, and hybrid search
for the GraphRAG pipeline. Uses lazy imports so the module compiles
even when qdrant-client is not installed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


@dataclass
class QdrantPoint:
    """A point in the Qdrant vector store with payload and sparse vector support."""

    id: str
    vector: list[float]
    sparse_vector: Optional[dict[str, Any]] = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class QdrantSearchResult:
    """A search result from Qdrant with score and payload."""

    id: str
    score: float
    payload: dict[str, Any]
    version: int = 1


class QdrantError(Exception):
    """Base exception for Qdrant operations."""


class QdrantConnectionError(QdrantError):
    """Raised when connection to Qdrant fails."""


class QdrantCollectionError(QdrantError):
    """Raised when a collection operation fails."""


class QdrantVectorStore:
    """Production-grade async Qdrant vector store adapter.

    Handles dense vector indexing, payload filtering, hybrid search,
    collection lifecycle, and connection management with retry logic.
    """

    def __init__(
        self,
        collection_name: str = "knowledge_graph",
        vector_size: int = 1536,
        host: Optional[str] = None,
        port: Optional[int] = None,
        grpc_port: Optional[int] = None,
        prefer_grpc: bool = False,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._host = host or getattr(settings, "qdrant_host", "localhost")
        self._port = port or getattr(settings, "qdrant_port", 6333)
        self._grpc_port = grpc_port or getattr(settings, "qdrant_grpc_port", 6334)
        self._prefer_grpc = prefer_grpc
        self._api_key = api_key or getattr(settings, "qdrant_api_key", None)
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Any = None
        self._async_client: Any = None
        self._initialized = False

    async def connect(self) -> None:
        """Initialize the Qdrant async client with retry logic."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                from qdrant_client import AsyncQdrantClient

                args: dict[str, Any] = {
                    "host": self._host,
                    "port": self._grpc_port if self._prefer_grpc else self._port,
                    "prefer_grpc": self._prefer_grpc,
                    "timeout": self._timeout,
                }
                if self._api_key:
                    args["api_key"] = self._api_key
                self._async_client = AsyncQdrantClient(**args)
                await self._async_client.get_collections()
                self._initialized = True
                logger.info("Connected to Qdrant at %s:%s", self._host, self._port)
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    "Qdrant connection attempt %d/%d failed: %s",
                    attempt, self._max_retries, str(e),
                )
                if attempt < self._max_retries:
                    import asyncio

                    await asyncio.sleep(2**attempt)
        raise QdrantConnectionError(
            f"Failed to connect to Qdrant after {self._max_retries} attempts: {last_error}",
        )

    async def disconnect(self) -> None:
        """Close the Qdrant client connection."""
        if self._async_client:
            try:
                await self._async_client.close()
            except Exception as e:
                logger.warning("Error closing Qdrant client: %s", str(e))
            self._async_client = None
            self._initialized = False

    async def ensure_collection(
        self,
        *,
        recreate: bool = False,
        hnsw_config: Optional[dict[str, Any]] = None,
        quantization_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Create or reconfigure the collection with optimal defaults.

        Args:
            recreate: Drop and recreate if exists.
            hnsw_config: HNSW index configuration overrides.
            quantization_config: Scalar/product quantization config.

        Returns:
            Dict with operation status.
        """
        self._require_connected()
        from qdrant_client.models import (
            Distance,
            HnswConfigDiff,
            QuantizationConfig,
            ScalarQuantization,
            VectorParams,
        )

        try:
            collections = await self._async_client.get_collections()
            exists = any(
                c.name == self._collection_name for c in collections.collections
            )

            if recreate and exists:
                await self._async_client.delete_collection(
                    collection_name=self._collection_name,
                )
                exists = False

            if not exists:
                default_hnsw = HnswConfigDiff(
                    m=16,
                    ef_construct=200,
                    full_scan_threshold=10000,
                    **(hnsw_config or {}),
                )
                default_quant = quantization_config or QuantizationConfig(
                    scalar=ScalarQuantization(
                        type="scalar",
                        quantile=0.99,
                        always_ram=True,
                    ),
                )
                await self._async_client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(
                        size=self._vector_size,
                        distance=Distance.COSINE,
                        hnsw_config=default_hnsw,
                        quantization_config=default_quant,
                    ),
                )
                logger.info("Created Qdrant collection '%s'", self._collection_name)
                return {"created": True, "recreated": recreate}

            logger.debug("Qdrant collection '%s' already exists", self._collection_name)
            return {"created": False, "recreated": False}
        except Exception as e:
            raise QdrantCollectionError(
                f"Failed to ensure collection '{self._collection_name}': {e}",
            ) from e

    async def upsert_points(
        self,
        points: list[QdrantPoint],
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """Upsert points in batches with progress logging.

        Args:
            points: Points to upsert.
            batch_size: Number of points per batch.

        Returns:
            Dict with counts and status.
        """
        self._require_connected()
        from qdrant_client.models import PointStruct

        total = len(points)
        inserted = 0
        errors: list[str] = []

        for i in range(0, total, batch_size):
            batch = points[i : i + batch_size]
            try:
                point_structs = [
                    PointStruct(
                        id=p.id,
                        vector=p.vector,
                        payload=p.payload,
                    )
                    for p in batch
                ]
                await self._async_client.upsert(
                    collection_name=self._collection_name,
                    points=point_structs,
                )
                inserted += len(batch)
            except Exception as e:
                error_msg = f"Batch {i // batch_size} failed: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

            if (i + batch_size) % (batch_size * 10) == 0 or i + batch_size >= total:
                logger.info(
                    "Upserted %d/%d points to Qdrant", min(i + batch_size, total), total,
                )

        return {
            "total": total,
            "inserted": inserted,
            "errors": errors,
            "error_count": len(errors),
        }

    async def search(
        self,
        vector: list[float],
        *,
        top_k: int = 20,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[dict[str, Any]] = None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> list[QdrantSearchResult]:
        """Dense vector search with optional payload filtering.

        Args:
            vector: Query embedding vector.
            top_k: Maximum results.
            score_threshold: Minimum similarity score.
            filter_conditions: Qdrant filter conditions.
            with_payload: Include payload in results.
            with_vectors: Include vectors in results.

        Returns:
            Ranked list of search results.
        """
        self._require_connected()
        from qdrant_client.models import Filter

        try:
            filter_obj = None
            if filter_conditions:
                filter_obj = Filter(**self._build_qdrant_filter(filter_conditions))

            results = await self._async_client.search(
                collection_name=self._collection_name,
                query_vector=vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=filter_obj,
                with_payload=with_payload,
                with_vectors=with_vectors,
            )
            return [
                QdrantSearchResult(
                    id=str(r.id),
                    score=r.score,
                    payload=r.payload or {},
                    version=1,
                )
                for r in results
            ]
        except Exception as e:
            raise QdrantError(f"Qdrant search failed: {e}") from e

    async def search_batch(
        self,
        vectors: list[list[float]],
        *,
        top_k: int = 20,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[list[QdrantSearchResult]]:
        """Batch dense search for multiple query vectors."""
        self._require_connected()
        from qdrant_client.models import Filter, models

        try:
            filter_obj = None
            if filter_conditions:
                filter_obj = Filter(**self._build_qdrant_filter(filter_conditions))

            results = await self._async_client.search_batch(
                collection_name=self._collection_name,
                requests=[
                    models.SearchRequest(
                        vector=v,
                        limit=top_k,
                        filter=filter_obj,
                        with_payload=True,
                    )
                    for v in vectors
                ],
            )
            return [
                [
                    QdrantSearchResult(
                        id=str(r.id),
                        score=r.score,
                        payload=r.payload or {},
                    )
                    for r in batch
                ]
                for batch in results
            ]
        except Exception as e:
            raise QdrantError(f"Qdrant batch search failed: {e}") from e

    async def scroll(
        self,
        *,
        filter_conditions: Optional[dict[str, Any]] = None,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> tuple[list[QdrantSearchResult], Optional[str]]:
        """Scroll through points with optional filter."""
        self._require_connected()
        try:
            results, next_offset = await self._async_client.scroll(
                collection_name=self._collection_name,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            points = [
                QdrantSearchResult(
                    id=str(p.id),
                    score=1.0,
                    payload=p.payload or {},
                )
                for p in results
            ]
            return points, str(next_offset) if next_offset else None
        except Exception as e:
            raise QdrantError(f"Qdrant scroll failed: {e}") from e

    async def delete_points(
        self,
        point_ids: Optional[list[str]] = None,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> int:
        """Delete points by ID or filter."""
        self._require_connected()
        from qdrant_client import models
        try:
            if point_ids:
                result = await self._async_client.delete(
                    collection_name=self._collection_name,
                    points_selector=models.PointIdsList(
                        points=point_ids,
                    ),
                )
            elif filter_conditions:
                from qdrant_client.models import Filter

                result = await self._async_client.delete(
                    collection_name=self._collection_name,
                    points_selector=models.FilterSelector(
                        filter=Filter(**self._build_qdrant_filter(filter_conditions)),
                    ),
                )
            else:
                raise ValueError("Either point_ids or filter_conditions required")
            return getattr(result, "count", len(point_ids or []))
        except Exception as e:
            raise QdrantError(f"Qdrant delete failed: {e}") from e

    async def count_points(
        self,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> int:
        """Count points in collection with optional filter."""
        self._require_connected()
        try:
            result = await self._async_client.count(
                collection_name=self._collection_name,
                count_filter=(
                    Filter(**self._build_qdrant_filter(filter_conditions))
                    if filter_conditions
                    else None
                ),
                exact=True,
            )
            return result.count
        except Exception as e:
            raise QdrantError(f"Qdrant count failed: {e}") from e

    async def info(self) -> dict[str, Any]:
        """Get collection info with point count and vector config."""
        self._require_connected()
        try:
            info = await self._async_client.get_collection(
                collection_name=self._collection_name,
            )
            return {
                "collection_name": self._collection_name,
                "vector_size": info.config.params.vectors.size,
                "distance": str(info.config.params.vectors.distance),
                "point_count": info.points_count,
                "indexed_vector_count": info.indexed_vectors_count,
                "status": str(info.status),
            }
        except Exception as e:
            raise QdrantError(f"Failed to get collection info: {e}") from e

    def _require_connected(self) -> None:
        if not self._initialized or not self._async_client:
            raise QdrantConnectionError("Qdrant not connected. Call connect() first.")

    @staticmethod
    def _build_qdrant_filter(
        conditions: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a Qdrant-compatible filter from a simple key-value dict.

        Converts: {"field": "value"} -> {"should": [{"key": "field", "match": {"value": "value"}}]}
        Supports: lists (OR within field), dicts for range/nested.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

        should: list[FieldCondition] = []
        for key, value in conditions.items():
            if isinstance(value, dict):
                if "gte" in value or "lte" in value:
                    should.append(
                        FieldCondition(
                            key=key,
                            range=Range(
                                gte=value.get("gte"),
                                lte=value.get("lte"),
                                gt=value.get("gt"),
                                lt=value.get("lt"),
                            ),
                        ),
                    )
                else:
                    for sub_key, sub_value in value.items():
                        should.append(
                            FieldCondition(
                                key=f"{key}.{sub_key}",
                                match=MatchValue(value=sub_value),
                            ),
                        )
            elif isinstance(value, list):
                inner: list[FieldCondition] = [
                    FieldCondition(key=key, match=MatchValue(v)) for v in value
                ]
                should.extend(inner)
            else:
                should.append(
                    FieldCondition(key=key, match=MatchValue(value=value)),
                )
        return {"should": should}
