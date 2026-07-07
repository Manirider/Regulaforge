from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from regulaforge.ingestion.application.etl_service import ETLService
from regulaforge.ingestion.application.fingerprint_service import FingerprintCalculator
from regulaforge.ingestion.domain.events import (
    CrawlCompleted,
    CrawlStarted,
    DocumentDownloaded,
    DocumentDuplicateFound,
)
from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlSourceConfig,
    CrawlSourceType,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.domain.repository import (
    CrawlJobRepository,
    DocumentRepository,
    FingerprintRepository,
)
from regulaforge.ingestion.infrastructure.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class CrawlerService:
    def __init__(
        self,
        crawlers: dict[CrawlSourceType, BaseCrawler],
        doc_repo: DocumentRepository,
        fp_repo: FingerprintRepository,
        job_repo: CrawlJobRepository,
        etl_service: ETLService,
        fingerprint_calculator: FingerprintCalculator,
        configs: dict[CrawlSourceType, CrawlSourceConfig],
        raw_dir: Path,
        text_dir: Path,
        concurrency: int = 4,
    ) -> None:
        self._crawlers = crawlers
        self._doc_repo = doc_repo
        self._fp_repo = fp_repo
        self._job_repo = job_repo
        self._etl = etl_service
        self._fp = fingerprint_calculator
        self._configs = configs
        self._raw_dir = raw_dir
        self._text_dir = text_dir
        self._concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _get_existing_hashes(self, source_type: CrawlSourceType) -> set[str]:
        hashes: set[str] = set()
        offset = 0
        limit = 500
        while True:
            docs, _ = await self._doc_repo.list(
                source_type=source_type,
                limit=limit,
                offset=offset,
            )
            if not docs:
                break
            for d in docs:
                if d.file_hash_sha256:
                    hashes.add(d.file_hash_sha256)
            offset += limit
        return hashes

    async def crawl_source(
        self,
        source_type: CrawlSourceType,
        incremental: bool = True,
    ) -> CrawlJob:
        crawler = self._crawlers[source_type]
        config = self._configs[source_type]
        job = CrawlJob(id=uuid4(), source_type=source_type)
        await self._job_repo.save(job)
        job.start()
        await self._job_repo.save(job)

        event = CrawlStarted(job_id=job.id, source_type=source_type, timestamp=job.started_at)
        logger.info("Crawl started: %s", event.to_dict())

        existing_hashes = await self._get_existing_hashes(source_type)
        last_run = None
        if incremental:
            last_run = await self._job_repo.get_last_successful_run(source_type)

        try:
            discovered = await crawler.discover_documents(
                config=config,
                since=last_run.started_at if last_run else None,
            )
            job.documents_found = len(discovered)
            logger.info("Discovered %d documents from %s", len(discovered), source_type.value)

            docs_to_download: list[RegulatoryDocument] = []
            for item in discovered:
                existing = await self._doc_repo.get_by_external_id(source_type, item.external_id)
                if existing and (existing.file_hash_sha256
                    and existing.file_hash_sha256 in existing_hashes):
                    continue
                doc = RegulatoryDocument(
                    id=uuid4(),
                    source_type=source_type,
                    external_id=item.external_id,
                    title=item.title,
                    category=item.category,
                    url=item.url,
                    published_date=item.published_date,
                    effective_date=item.effective_date,
                )
                docs_to_download.append(doc)

            logger.info("New documents to download from %s: %d", source_type.value, len(docs_to_download))

            for doc in docs_to_download:
                await self._doc_repo.save(doc)

            async def download_one(doc: RegulatoryDocument) -> None:
                async with self._semaphore:
                    try:
                        doc.status = DocumentStatus.DOWNLOADING
                        await self._doc_repo.save(doc)

                        file_path, file_size, sha256 = await crawler.download_document(
                            doc=doc,
                            config=config,
                            download_dir=self._raw_dir / source_type.value,
                        )

                        if sha256 in existing_hashes:
                            existing_doc = await self._doc_repo.get_by_file_hash(sha256)
                            if existing_doc and existing_doc.id != doc.id:
                                doc.mark_duplicate(existing_doc.id)
                                await self._doc_repo.save(doc)
                                job.documents_duplicate += 1
                                event_dup = DocumentDuplicateFound(
                                    document_id=doc.id,
                                    existing_document_id=existing_doc.id,
                                    source_type=source_type,
                                    external_id=doc.external_id,
                                    file_hash_sha256=sha256,
                                    timestamp=datetime.now(timezone.utc),
                                )
                                logger.info("Duplicate found: %s", event_dup.to_dict())
                                return

                        doc.mark_downloaded(str(file_path), file_size, sha256)
                        await self._doc_repo.save(doc)
                        job.documents_downloaded += 1

                        event_dl = DocumentDownloaded(
                            document_id=doc.id,
                            source_type=source_type,
                            external_id=doc.external_id,
                            title=doc.title,
                            file_size_bytes=file_size,
                            file_hash_sha256=sha256,
                            timestamp=datetime.now(timezone.utc),
                        )
                        logger.info("Downloaded: %s", event_dl.to_dict())

                        await self._etl.etl_pipeline(doc, self._raw_dir / source_type.value, self._text_dir, job)

                    except Exception as exc:
                        logger.exception("Failed to download %s: %s", doc.external_id, exc)
                        doc.mark_failed()
                        await self._doc_repo.save(doc)
                        job.documents_failed += 1

            tasks = [download_one(d) for d in docs_to_download]
            await asyncio.gather(*tasks)

            duration = (datetime.now(timezone.utc) - job.started_at).total_seconds()
            job.complete()
            await self._job_repo.save(job)

            event_complete = CrawlCompleted(
                job_id=job.id,
                source_type=source_type,
                documents_found=job.documents_found,
                documents_downloaded=job.documents_downloaded,
                documents_failed=job.documents_failed,
                documents_duplicate=job.documents_duplicate,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc),
            )
            logger.info("Crawl completed: %s", event_complete.to_dict())

        except Exception as exc:
            logger.exception("Crawl failed for %s", source_type.value)
            job.fail(str(exc))
            await self._job_repo.save(job)

        return job

    async def crawl_all(self, incremental: bool = True) -> dict[CrawlSourceType, CrawlJob]:
        results: dict[CrawlSourceType, CrawlJob] = {}
        for source_type in CrawlSourceType:
            try:
                job = await self.crawl_source(source_type, incremental=incremental)
                results[source_type] = job
            except Exception:
                logger.exception("Crawl all failed for %s", source_type.value)
        return results
