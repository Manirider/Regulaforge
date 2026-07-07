from __future__ import annotations

import logging
from collections.abc import Callable

from regulaforge.ingestion.domain.models import CrawlSourceConfig, CrawlSourceType

logger = logging.getLogger(__name__)


class SchedulerAdapter:
    def __init__(self) -> None:
        self._scheduler = None

    def start(
        self,
        crawl_fn: Callable,
        configs: dict[CrawlSourceType, CrawlSourceConfig],
    ) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            logger.warning("APScheduler not installed. Install with: pip install apscheduler")
            return

        self._scheduler = AsyncIOScheduler()

        for cfg in configs.values():
            if not cfg.enabled:
                continue
            self._scheduler.add_job(
                crawl_fn,
                trigger=IntervalTrigger(minutes=cfg.crawl_interval_minutes),
                args=[cfg.source_type],
                id=f"crawl_{cfg.source_type.value}",
                replace_existing=True,
                name=f"{cfg.source_type.value.upper()} Crawl",
                misfire_grace_time=300,
            )
            logger.info(
                "Scheduled %s crawl: interval=%d min",
                cfg.source_type.value,
                cfg.crawl_interval_minutes,
            )

        self._scheduler.start()
        logger.info("Scheduler started successfully")

    def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    @property
    def running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running
