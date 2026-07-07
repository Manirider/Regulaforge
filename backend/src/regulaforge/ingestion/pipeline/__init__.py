"""
Pipeline package for the RegulaForge ingestion subsystem.

Provides production-grade primitives for executing the document ingestion
workflow: configurable retry with exponential backoff and jitter, a parallel
streaming downloader with hash verification, and an APScheduler-based job
scheduler for recurring crawl operations.

All I/O is fully async (asyncio + aiohttp + aiofiles).
"""

from regulaforge.ingestion.pipeline.retry import RetryConfig, retry_with_backoff, calculate_backoff
from regulaforge.ingestion.pipeline.downloader import ParallelDownloader, DownloadRequest, DownloadResult
from regulaforge.ingestion.pipeline.scheduler import PipelineScheduler, ScheduledJob

__all__ = [
    "RetryConfig",
    "retry_with_backoff",
    "calculate_backoff",
    "ParallelDownloader",
    "DownloadRequest",
    "DownloadResult",
    "PipelineScheduler",
    "ScheduledJob",
]
