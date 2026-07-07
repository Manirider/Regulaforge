from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin

import aiohttp
from bs4 import BeautifulSoup

from regulaforge.ingestion.domain.models import (
    CrawlSourceConfig,
    DocumentCategory,
    RegulatoryDocument,
)
from regulaforge.ingestion.infrastructure.crawlers.base_crawler import (
    BaseCrawler,
    DiscoveredDocument,
    RetryExhausted,
)

logger = __import__("logging").getLogger(__name__)

SEBI_BASE = "https://www.sebi.gov.in"
SEBI_CIRCULARS_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?dllHome=yes&dllSec=Circulars"


class SEBICrawler(BaseCrawler):

    async def discover_documents(
        self,
        config: CrawlSourceConfig,
        _since: datetime | None = None,
    ) -> list[DiscoveredDocument]:
        documents: list[DiscoveredDocument] = []
        page = 1
        seen_ids: set = set()

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    params = {"pageNo": str(page)}
                    url = f"{SEBI_BASE}/sebiweb/{(urlencode(params))}&dllHome=yes&dllSec=Circulars"
                    if page == 1:
                        url = SEBI_CIRCULARS_URL
                    resp = await self._fetch_with_retry(session, url, config)
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    items = soup.select("table tr, .circular-list li, .list-item")

                    if not items:
                        items = soup.find_all("div", {"class": re.compile(r"item|cricular|doc")})

                    if not items:
                        break

                    found_new = False
                    for item in items:
                        link = item.find("a") if hasattr(item, "find") else None
                        if not link or not link.get("href"):
                            continue
                        href = link["href"]
                        title = link.get_text(strip=True)
                        if not title:
                            continue

                        full_url = urljoin(SEBI_BASE, href) if not href.startswith("http") else href
                        external_id = hashlib.md5(href.encode()).hexdigest()[:12]
                        if external_id in seen_ids:
                            continue
                        seen_ids.add(external_id)

                        date_text = ""
                        date_tag = item.find("span", {"class": re.compile(r"date|time")}) or item.find("small")
                        if date_tag:
                            date_text = date_tag.get_text(strip=True)

                        published_date = self._parse_date(date_text, ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"]) or datetime.now(timezone.utc)  # noqa: E501
                        category = self._categorize(title)
                        doc = DiscoveredDocument(
                            external_id=external_id,
                            title=title,
                            url=full_url,
                            category=category,
                            published_date=published_date,
                        )
                        documents.append(doc)
                        found_new = True

                    if not found_new:
                        break
                    page += 1
                    if page > 50:
                        break

                except RetryExhausted as exc:
                    logger.error("SEBI discovery failed: %s", exc)
                    raise

        logger.info("SEBI discovery found %d documents", len(documents))
        return documents

    async def download_document(
        self,
        doc: RegulatoryDocument,
        config: CrawlSourceConfig,
        download_dir: Path,
    ) -> tuple[Path, int, str]:
        file_name = f"{doc.external_id}.pdf"
        target_path = download_dir / file_name

        async with aiohttp.ClientSession() as session:
            try:
                file_size, sha256 = await self._download_file_with_retry(session, doc.url, target_path, config)
                return target_path, file_size, sha256
            except RetryExhausted:
                raise

    def _categorize(self, title: str) -> DocumentCategory:
        t = title.lower()
        if "circular" in t:
            return DocumentCategory.CIRCULAR
        if "master direction" in t:
            return DocumentCategory.MASTER_DIRECTION
        if "notification" in t:
            return DocumentCategory.NOTIFICATION
        if "guideline" in t:
            return DocumentCategory.GUIDELINE
        if "press release" in t:
            return DocumentCategory.PRESS_RELEASE
        if "report" in t or "annual" in t:
            return DocumentCategory.REPORT
        if "amendment" in t or "amend" in t:
            return DocumentCategory.AMENDMENT
        return DocumentCategory.OTHER
