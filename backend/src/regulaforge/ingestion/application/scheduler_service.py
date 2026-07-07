from __future__ import annotations

import logging

from regulaforge.ingestion.application.crawler_service import CrawlerService
from regulaforge.ingestion.domain.models import CrawlSourceConfig, CrawlSourceType

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(
        self,
        crawler_service: CrawlerService,
        configs: dict[CrawlSourceType, CrawlSourceConfig],
    ) -> None:
        self._crawler_service = crawler_service
        self._configs = configs
        self._scheduler = None

    def start(self) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            logger.warning("APScheduler not installed, scheduler disabled")
            return

        self._scheduler = AsyncIOScheduler()

        for cfg in self._configs.values():
            if not cfg.enabled:
                continue
            self._scheduler.add_job(
                self._run_crawl,
                trigger=IntervalTrigger(minutes=cfg.crawl_interval_minutes),
                args=[cfg.source_type],
                id=f"crawl_{cfg.source_type.value}",
                replace_existing=True,
                name=f"{cfg.source_type.value.upper()} Crawl",
            )
            logger.info(
                "Scheduled %s crawl every %d minutes",
                cfg.source_type.value,
                cfg.crawl_interval_minutes,
            )

        self._scheduler.start()
        logger.info("Scheduler started")

    async def _run_crawl(self, source_type: CrawlSourceType) -> None:
        logger.info("Scheduled crawl starting for %s", source_type.value)
        try:
            await self._crawler_service.crawl_source(source_type, incremental=True)
        except Exception as exc:
            logger.exception("Scheduled crawl failed for %s: %s", source_type.value, exc)

    async def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    async def run_once(self, source_type: CrawlSourceType) -> None:
        await self._crawler_service.crawl_source(source_type, incremental=True)
