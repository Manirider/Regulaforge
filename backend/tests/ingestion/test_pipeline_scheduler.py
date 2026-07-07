from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from regulaforge.ingestion.domain.models import CrawlSourceType
from regulaforge.ingestion.pipeline.scheduler import PipelineScheduler


class TestPipelineScheduler:
    @pytest.fixture
    def scheduler(self) -> PipelineScheduler:
        return PipelineScheduler()

    def test_add_job_returns_id(self, scheduler: PipelineScheduler) -> None:
        job_id = scheduler.add_job(
            CrawlSourceType.RBI,
            lambda _: None,
            interval_minutes=60,
        )
        assert job_id == "rbi_crawl"

    def test_add_job_custom_id(self, scheduler: PipelineScheduler) -> None:
        job_id = scheduler.add_job(
            CrawlSourceType.SEBI,
            lambda _: None,
            interval_minutes=30,
            job_id="my_sebi_job",
        )
        assert job_id == "my_sebi_job"

    def test_get_jobs_initial(self, scheduler: PipelineScheduler) -> None:
        assert scheduler.get_jobs() == []

    def test_get_jobs_after_add(self, scheduler: PipelineScheduler) -> None:
        scheduler.add_job(CrawlSourceType.RBI, lambda _: None, interval_minutes=60)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].source_type == CrawlSourceType.RBI
        assert jobs[0].interval_minutes == 60

    def test_get_job_by_id(self, scheduler: PipelineScheduler) -> None:
        scheduler.add_job(CrawlSourceType.IRDAI, lambda _: None, interval_minutes=180)
        job = scheduler.get_job("irdai_crawl")
        assert job is not None
        assert job.source_type == CrawlSourceType.IRDAI

    def test_get_nonexistent_job(self, scheduler: PipelineScheduler) -> None:
        assert scheduler.get_job("nonexistent") is None

    def test_remove_job(self, scheduler: PipelineScheduler) -> None:
        scheduler.add_job(CrawlSourceType.RBI, lambda _: None)
        scheduler.remove_job("rbi_crawl")
        assert scheduler.get_job("rbi_crawl") is None

    @pytest.mark.asyncio
    async def test_start_and_shutdown(self, scheduler: PipelineScheduler) -> None:
        assert not scheduler.running
        scheduler.start()
        assert scheduler.running
        scheduler.shutdown()
        await asyncio.sleep(0.1)
        assert not scheduler.running

    def test_pause_and_resume_job(self, scheduler: PipelineScheduler) -> None:
        scheduler.add_job(CrawlSourceType.RBI, lambda _: None)
        scheduler.pause_job("rbi_crawl")
        scheduler.resume_job("rbi_crawl")

    def test_multiple_jobs(self, scheduler: PipelineScheduler) -> None:
        scheduler.add_job(CrawlSourceType.RBI, lambda _: None, interval_minutes=60)
        scheduler.add_job(CrawlSourceType.SEBI, lambda _: None, interval_minutes=120)
        scheduler.add_job(CrawlSourceType.IRDAI, lambda _: None, interval_minutes=180)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 3
        intervals = sorted(j.interval_minutes for j in jobs)
        assert intervals == [60, 120, 180]

    def test_record_run_updates_last_run(self, scheduler: PipelineScheduler) -> None:
        scheduler.add_job(CrawlSourceType.RBI, lambda _: None)
        now = datetime.now(timezone.utc)
        scheduler.record_run("rbi_crawl")
        job = scheduler.get_job("rbi_crawl")
        assert job is not None
        assert job.last_run is not None
        assert (job.last_run - now).total_seconds() < 2

    def test_record_run_nonexistent_job_no_error(self, scheduler: PipelineScheduler) -> None:
        scheduler.record_run("nonexistent")

    def test_remove_job_cleans_up_tracker(self, scheduler: PipelineScheduler) -> None:
        scheduler.add_job(CrawlSourceType.RBI, lambda _: None)
        scheduler.record_run("rbi_crawl")
        scheduler.remove_job("rbi_crawl")
        assert scheduler.get_job("rbi_crawl") is None
