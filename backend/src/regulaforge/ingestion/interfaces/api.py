from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlSourceType,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.domain.repository import (
    CrawlJobRepository,
    DocumentRepository,
    FingerprintRepository,
)
from regulaforge.ingestion.monitoring.metrics import IngestionMetrics

logger = logging.getLogger(__name__)


def create_ingestion_router(
    crawl_fn: Callable[[CrawlSourceType, bool], Awaitable[CrawlJob]] | None = None,
    crawl_all_fn: Callable[[bool], Awaitable[dict[CrawlSourceType, CrawlJob]]] | None = None,
    doc_repo: DocumentRepository | None = None,
    job_repo: CrawlJobRepository | None = None,
    fp_repo: FingerprintRepository | None = None,
    metrics: IngestionMetrics | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/ingestion", tags=["ingestion"])

    # ── Crawl endpoints ───────────────────────────────────────────────

    @router.post("/crawl/{source_type}")
    async def trigger_crawl(
        source_type: CrawlSourceType,
        incremental: bool = Query(True, description="Incremental crawl"),
    ) -> dict[str, str]:
        if crawl_fn is None:
            raise HTTPException(500, "Crawler service not configured")
        job = await crawl_fn(source_type, incremental=incremental)
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "source_type": source_type.value,
        }

    @router.post("/crawl")
    async def trigger_crawl_all(
        incremental: bool = Query(True, description="Incremental crawl for all sources"),
    ) -> dict[str, str]:
        if crawl_all_fn is None:
            raise HTTPException(500, "Crawler service not configured")
        results = await crawl_all_fn(incremental=incremental)
        return {k.value: str(v.id) for k, v in results.items()}

    @router.post("/crawl/{source_type}/force")
    async def force_crawl(source_type: CrawlSourceType) -> dict[str, str]:
        if crawl_fn is None:
            raise HTTPException(500, "Crawler service not configured")
        job = await crawl_fn(source_type, incremental=False)
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "source_type": source_type.value,
        }

    # ── Job endpoints ─────────────────────────────────────────────────

    @router.get("/jobs", response_model=dict)
    async def list_jobs(
        source_type: CrawlSourceType | None = None,
        status: str | None = None,
        limit: int = Query(50, le=200),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        if job_repo is None:
            raise HTTPException(500, "Job repository not configured")
        jobs, total = await job_repo.list(
            source_type=source_type,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "jobs": [j.to_dict() for j in jobs],
        }

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: UUID) -> dict[str, Any]:
        if job_repo is None:
            raise HTTPException(500, "Job repository not configured")
        job = await job_repo.get_by_id(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job.to_dict()

    @router.get("/jobs/last/{source_type}")
    async def get_last_job(source_type: CrawlSourceType) -> dict[str, Any] | None:
        if job_repo is None:
            raise HTTPException(500, "Job repository not configured")
        job = await job_repo.get_last_run(source_type)
        if not job:
            return None
        return job.to_dict()

    # ── Document endpoints ────────────────────────────────────────────

    @router.get("/documents", response_model=dict)
    async def list_documents(
        source_type: CrawlSourceType | None = None,
        category: str | None = None,
        status: DocumentStatus | None = None,
        limit: int = Query(100, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        if doc_repo is None:
            raise HTTPException(500, "Document repository not configured")
        docs, total = await doc_repo.list(
            source_type=source_type,
            category=category,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "documents": [d.to_dict() for d in docs],
        }

    @router.get("/documents/{doc_id}")
    async def get_document(doc_id: UUID) -> dict[str, Any]:
        if doc_repo is None:
            raise HTTPException(500, "Document repository not configured")
        doc = await doc_repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        return doc.to_dict()

    @router.get("/documents/external/{source_type}/{external_id}")
    async def get_document_by_external_id(
        source_type: CrawlSourceType, external_id: str
    ) -> dict[str, Any]:
        if doc_repo is None:
            raise HTTPException(500, "Document repository not configured")
        doc = await doc_repo.get_by_external_id(source_type, external_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        return doc.to_dict()

    @router.get("/documents/{doc_id}/fingerprint")
    async def get_document_fingerprint(doc_id: UUID) -> dict[str, Any] | None:
        if fp_repo is None:
            raise HTTPException(500, "Fingerprint repository not configured")
        fp = await fp_repo.get_by_document_id(doc_id)
        if not fp:
            raise HTTPException(404, "Fingerprint not found")
        return {
            "id": str(fp.id),
            "document_id": str(fp.document_id),
            "file_hash_sha256": fp.file_hash_sha256,
            "content_hash": fp.content_hash,
            "simhash": fp.simhash,
            "num_tokens": fp.num_tokens,
            "created_at": fp.created_at.isoformat(),
        }

    # ── Stats endpoints ───────────────────────────────────────────────

    @router.get("/stats")
    async def get_stats() -> dict[str, Any]:
        if doc_repo is None or job_repo is None:
            raise HTTPException(500, "Repositories not configured")
        stats: dict[str, Any] = {}
        for st in CrawlSourceType:
            count = await doc_repo.count_by_source(st)
            last_job = await job_repo.get_last_run(st)
            stats[st.value] = {
                "document_count": count,
                "last_crawl": last_job.to_dict() if last_job else None,
            }
        return stats

    @router.get("/stats/metrics")
    async def get_metrics() -> dict[str, Any]:
        if metrics is None:
            raise HTTPException(500, "Metrics not configured")
        return metrics.snapshot()

    @router.get("/stats/health")
    async def get_health() -> dict[str, str]:
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return router
