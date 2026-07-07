"""
APScheduler-based job scheduler for recurring crawl operations.

Wraps ``AsyncIOScheduler`` with a simplified API for adding, removing,
pausing, and resuming crawl jobs per regulatory source type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from regulaforge.ingestion.domain.models import CrawlSourceType


@dataclass
class ScheduledJob:
    """Descriptor for a registered crawl job.

    Attributes:
        job_id: Unique identifier for the job.
        source_type: Regulatory source this job crawls.
        interval_minutes: How often the job should run.
        next_run: Next scheduled execution time (populated by ``get_jobs``).
        last_run: Most recent execution time (populated by ``get_jobs``).
    """

    job_id: str
    source_type: CrawlSourceType
    interval_minutes: int
    next_run: datetime | None = None
    last_run: datetime | None = None


JobCallback = Callable[[CrawlSourceType], Awaitable[None]]
"""Signature: ``callback(source_type)``."""


class PipelineScheduler:
    """Manages scheduled crawl jobs using APScheduler.

    The scheduler is lazily started via ``start()`` and must be shut down
    with ``shutdown()`` for clean resource release.
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._jobs: dict[str, ScheduledJob] = {}
        self._last_run_tracker: dict[str, datetime] = {}

    def add_job(
        self,
        source_type: CrawlSourceType,
        callback: JobCallback,
        interval_minutes: int = 60,
        job_id: str | None = None,
    ) -> str:
        """Register a new crawl job.

        Args:
            source_type: Regulatory source to crawl.
            callback: Async callable invoked when the job fires.
            interval_minutes: Interval between runs.
            job_id: Optional custom ID (defaults to ``{source_type}_crawl``).

        Returns:
            The job ID.
        """
        actual_id = job_id or f"{source_type.value}_crawl"
        trigger = IntervalTrigger(minutes=interval_minutes)

        self._scheduler.add_job(
            func=callback,
            trigger=trigger,
            args=[source_type],
            id=actual_id,
            replace_existing=True,
            name=f"{source_type.value}_crawl",
            next_run_time=None,
        )

        self._jobs[actual_id] = ScheduledJob(
            job_id=actual_id,
            source_type=source_type,
            interval_minutes=interval_minutes,
        )
        return actual_id

    def remove_job(self, job_id: str) -> None:
        """Remove a scheduled job by ID. No-op if the job does not exist."""
        if job_id in self._jobs:
            self._scheduler.remove_job(job_id)
            del self._jobs[job_id]
            self._last_run_tracker.pop(job_id, None)

    def pause_job(self, job_id: str) -> None:
        """Pause a scheduled job. It will not fire until resumed."""
        self._scheduler.pause_job(job_id)

    def resume_job(self, job_id: str) -> None:
        """Resume a previously paused job."""
        self._scheduler.resume_job(job_id)

    def record_run(self, job_id: str) -> None:
        """Record that a job has just completed a run.

        Called by the job callback after successful execution.
        """
        self._last_run_tracker[job_id] = datetime.now(timezone.utc)

    def start(self) -> None:
        """Start the APScheduler event loop.

        Safe to call multiple times (idempotent).
        """
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the scheduler, optionally waiting for running jobs."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)

    @property
    def running(self) -> bool:
        """True if the APScheduler event loop is active."""
        return self._scheduler.running

    def get_jobs(self) -> list[ScheduledJob]:
        """Return a snapshot of all registered jobs with their timings."""
        now = datetime.now(timezone.utc)
        result: list[ScheduledJob] = []
        for job_id, info in self._jobs.items():
            aps_job = self._scheduler.get_job(job_id)
            next_run = aps_job.next_run_time if aps_job else None
            last_run = self._last_run_tracker.get(job_id)
            result.append(
                ScheduledJob(
                    job_id=job_id,
                    source_type=info.source_type,
                    interval_minutes=info.interval_minutes,
                    next_run=next_run,
                    last_run=last_run,
                )
            )
        return result

    def get_job(self, job_id: str) -> ScheduledJob | None:
        """Return a single job by ID, or None if not found."""
        info = self._jobs.get(job_id)
        if not info:
            return None
        aps_job = self._scheduler.get_job(job_id)
        last_run = self._last_run_tracker.get(job_id)
        return ScheduledJob(
            job_id=job_id,
            source_type=info.source_type,
            interval_minutes=info.interval_minutes,
            next_run=aps_job.next_run_time if aps_job else None,
            last_run=last_run,
        )
