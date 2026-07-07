from __future__ import annotations

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiohttp

from regulaforge.ingestion.domain.models import (
    CrawlSourceConfig,
    DocumentCategory,
    RegulatoryDocument,
)

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredDocument:
    external_id: str
    title: str
    url: str
    category: DocumentCategory
    published_date: datetime
    effective_date: datetime | None = None
    checksum: str | None = None


class RetryExhausted(Exception):  # noqa: N818
    pass


class BaseCrawler(ABC):

    @abstractmethod
    async def discover_documents(
        self,
        config: CrawlSourceConfig,
        since: datetime | None = None,
    ) -> list[DiscoveredDocument]:
        ...

    @abstractmethod
    async def download_document(
        self,
        doc: RegulatoryDocument,
        config: CrawlSourceConfig,
        download_dir: Path,
    ) -> tuple[Path, int, str]:
        ...

    async def _fetch_with_retry(
        self,
        session: aiohttp.ClientSession,
        url: str,
        config: CrawlSourceConfig,
        headers: dict | None = None,
    ) -> aiohttp.ClientResponse:
        last_exc: Exception | None = None
        req_headers = {
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/pdf,*/*",
        }
        if headers:
            req_headers.update(headers)

        for attempt in range(1, config.max_retries + 1):
            try:
                async with session.get(
                    url,
                    headers=req_headers,
                    timeout=aiohttp.ClientTimeout(total=config.request_timeout_seconds),
                    allow_redirects=True,
                ) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", str(config.retry_delay_seconds)))
                        logger.warning("Rate limited on %s, waiting %ds (attempt %d/%d)", url, retry_after, attempt, config.max_retries)  # noqa: E501
                        await asyncio.sleep(retry_after)
                        continue
                    resp.raise_for_status()
                    return resp
            except TimeoutError as exc:
                last_exc = exc
                logger.warning("Timeout fetching %s (attempt %d/%d)", url, attempt, config.max_retries)
            except aiohttp.ClientError as exc:
                last_exc = exc
                logger.warning("HTTP error fetching %s: %s (attempt %d/%d)", url, exc, attempt, config.max_retries)

            if attempt < config.max_retries:
                await asyncio.sleep(config.retry_delay_seconds * attempt)

        raise RetryExhausted(f"Failed to fetch {url} after {config.max_retries} attempts") from last_exc

    async def _download_file_with_retry(
        self,
        session: aiohttp.ClientSession,
        url: str,
        target_path: Path,
        config: CrawlSourceConfig,
    ) -> tuple[int, str]:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        last_exc: Exception | None = None

        for attempt in range(1, config.max_retries + 1):
            try:
                async with session.get(
                    url,
                    headers={"User-Agent": config.user_agent},
                    timeout=aiohttp.ClientTimeout(total=config.request_timeout_seconds * 2),
                ) as resp:
                    resp.raise_for_status()
                    sha256 = hashlib.sha256()
                    total_bytes = 0
                    with open(target_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(65536):
                            f.write(chunk)
                            sha256.update(chunk)
                            total_bytes += len(chunk)
                    return total_bytes, sha256.hexdigest()
            except (TimeoutError, aiohttp.ClientError, OSError) as exc:
                last_exc = exc
                logger.warning("Download failed %s (attempt %d/%d): %s", url, attempt, config.max_retries, exc)
                if target_path.exists():
                    target_path.unlink(missing_ok=True)
                if attempt < config.max_retries:
                    await asyncio.sleep(config.retry_delay_seconds * attempt)

        raise RetryExhausted(f"Failed to download {url} after {config.max_retries} attempts") from last_exc

    def _parse_date(self, date_str: str, formats: list[str]) -> datetime | None:
        from datetime import datetime as dt
        for fmt in formats:
            try:
                return dt.strptime(date_str.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        logger.debug("Could not parse date: %s", date_str)
        return None
